from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics import AnalyticsRepository
from app.repositories.promotion_signals import PromotionSignalsRepository
from app.schemas.marketing import (
    PromotionProductScore,
    PromotionSuggestionResponse,
)
from app.schemas.product import ProductResponse
from app.services.product import ProductService

MINIMUM_PROMOTION_MARGIN_RATE = 0.15


class PromotionScoringService:
    """Deterministic, explainable product selection for Marketing Agent."""

    def __init__(self, session: AsyncSession) -> None:
        self.analytics = AnalyticsRepository(session)
        self.signals = PromotionSignalsRepository(session)
        self.products = ProductService()

    async def suggest(
        self,
        *,
        promotion_kind: str,
        product_ids: list[int] | None = None,
    ) -> PromotionSuggestionResponse:
        now = datetime.now(UTC)
        catalogue = await self.products.list_products(
            page=1,
            page_size=500,
            search=None,
            brand=None,
            ingredient=None,
            category=None,
            flavor=None,
            min_price=None,
            max_price=None,
            in_stock=True,
            sort_by="stock_desc",
        )
        candidates = [
            product
            for product in catalogue.items
            if product.is_active and product.stock > 0 and product.price
        ]
        if not candidates:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "No active in-stock products are available for promotion",
            )

        sales_90 = await self.analytics.top_products(
            now - timedelta(days=90), now, limit=500
        )
        sales_30 = await self.analytics.top_products(
            now - timedelta(days=30), now, limit=500
        )
        previous_30 = await self.analytics.top_products(
            now - timedelta(days=60), now - timedelta(days=30), limit=500
        )
        pairs = await self.analytics.co_purchase_pairs(
            now - timedelta(days=180), now, limit=500
        )
        eligible_product_ids = [product.product_id for product in candidates]
        costs = await self.signals.cost_map(eligible_product_ids)
        views_90 = await self.signals.view_counts(
            start=now - timedelta(days=90),
            end=now,
        )
        scored = self._score_products(
            candidates,
            sales_90=sales_90,
            sales_30=sales_30,
            previous_30=previous_30,
            views_90=views_90,
            costs=costs,
        )

        if product_ids:
            score_by_id = {item.product_id: item for item in scored}
            selected = [
                score_by_id[product_id]
                for product_id in product_ids
                if product_id in score_by_id
            ]
            if len(selected) != len(product_ids):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "One or more selected products are inactive or out of stock",
                )
        elif promotion_kind == "pack":
            selected = self._select_pack(scored, pairs)
        else:
            selected = scored[:1]

        expected = 2 if promotion_kind == "pack" else 1
        if len(selected) < expected:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Not enough eligible products to create this promotion",
            )

        regular_total = round(sum(item.price for item in selected), 2)
        default_discount = 12.0 if promotion_kind == "pack" else 8.0
        selected_costs = [costs.get(item.product_id) for item in selected]
        suggested_discount = default_discount
        margin_note = (
            "Marge minimale a confirmer: certains prix d'achat "
            "ne sont pas encore renseignes."
        )
        if all(cost is not None for cost in selected_costs):
            total_cost = sum(float(cost) for cost in selected_costs)
            minimum_revenue = total_cost / (
                1 - MINIMUM_PROMOTION_MARGIN_RATE
            )
            maximum_discount = max(
                0.0,
                (1 - minimum_revenue / regular_total) * 100,
            )
            suggested_discount = round(
                min(default_discount, maximum_discount),
                1,
            )
            margin_note = (
                f"Marge brute minimale de "
                f"{MINIMUM_PROMOTION_MARGIN_RATE * 100:.0f}% protegee."
            )
        return PromotionSuggestionResponse(
            promotion_kind=promotion_kind,
            products=selected,
            regular_total=regular_total,
            suggested_discount_percentage=suggested_discount,
            suggested_price=round(
                regular_total * (1 - suggested_discount / 100),
                2,
            ),
            currency=selected[0].currency,
            data_notes=[
                "Score: ventes 90 jours, dynamique 30 jours, stock, tendance, prix, conversion et marge disponible.",
                "Les packs favorisent aussi les produits achetes ensemble et les categories complementaires.",
                (
                    "Le taux de conversion utilise les vues produit enregistrees."
                    if views_90
                    else "Le suivi des vues vient de demarrer; la conversion se precisera avec le trafic."
                ),
                (
                    f"Prix d'achat disponible pour {len(costs)} produit(s); les autres marges restent a confirmer."
                ),
                margin_note,
                "Safety Agent controle le contenu avant activation.",
            ],
        )

    async def validate_discount_margin(
        self,
        *,
        products: list[PromotionProductScore],
        discount_percentage: float,
    ) -> None:
        costs = await self.signals.cost_map(
            [product.product_id for product in products]
        )
        if len(costs) != len(products):
            return
        regular_total = sum(product.price for product in products)
        discounted_total = regular_total * (
            1 - discount_percentage / 100
        )
        total_cost = sum(costs[product.product_id] for product in products)
        margin_rate = (
            (discounted_total - total_cost) / discounted_total
            if discounted_total > 0
            else -1
        )
        if margin_rate < MINIMUM_PROMOTION_MARGIN_RATE:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This discount would reduce the gross margin below 15%",
            )

    @staticmethod
    def _score_products(
        products: list[ProductResponse],
        *,
        sales_90: list[dict],
        sales_30: list[dict],
        previous_30: list[dict],
        views_90: dict[int, int] | None = None,
        costs: dict[int, float] | None = None,
    ) -> list[PromotionProductScore]:
        views_90 = views_90 or {}
        costs = costs or {}
        units_90 = {
            int(item["product_id"]): int(item["quantity"])
            for item in sales_90
        }
        units_30 = {
            int(item["product_id"]): int(item["quantity"])
            for item in sales_30
        }
        previous_units = {
            int(item["product_id"]): int(item["quantity"])
            for item in previous_30
        }
        max_90 = max(units_90.values(), default=1)
        max_30 = max(units_30.values(), default=1)
        max_stock = max((product.stock for product in products), default=1)
        max_price = max(
            (float(product.price or 0) for product in products),
            default=1,
        )
        conversion_rates = {
            product.product_id: min(
                units_90.get(product.product_id, 0)
                / max(views_90.get(product.product_id, 0), 1),
                1,
            )
            for product in products
            if views_90.get(product.product_id, 0)
        }
        max_conversion = max(conversion_rates.values(), default=1)
        scored = []
        for product in products:
            product_id = product.product_id
            sold_90 = units_90.get(product_id, 0)
            sold_30 = units_30.get(product_id, 0)
            sold_previous = previous_units.get(product_id, 0)
            trend = max(sold_30 - sold_previous, 0)
            trend_score = min(trend / max(sold_previous, 1), 1)
            sales_score = sold_90 / max_90
            momentum_score = sold_30 / max_30
            stock_score = min(product.stock / max_stock, 1)
            price_score = 1 - min(float(product.price or 0) / max_price, 1)
            conversion_score = (
                conversion_rates.get(product_id, 0) / max_conversion
            )
            cost_price = costs.get(product_id)
            margin_rate = (
                max(
                    (float(product.price or 0) - cost_price)
                    / max(float(product.price or 0), 1),
                    0,
                )
                if cost_price is not None
                else 0
            )
            margin_score = min(margin_rate / 0.5, 1)
            score = round(
                100
                * (
                    sales_score * 0.27
                    + momentum_score * 0.15
                    + stock_score * 0.18
                    + trend_score * 0.10
                    + price_score * 0.08
                    + conversion_score * 0.12
                    + margin_score * 0.10
                ),
                1,
            )
            reasons = []
            if sold_90:
                reasons.append(f"{sold_90} unite(s) vendue(s) sur 90 jours")
            if sold_30 > sold_previous:
                reasons.append("demande recente en hausse")
            if product.stock >= 20:
                reasons.append(f"stock confortable: {product.stock}")
            if views_90.get(product_id):
                reasons.append(
                    f"conversion observee: {conversion_rates[product_id] * 100:.1f}%"
                )
            if cost_price is not None:
                reasons.append(
                    f"marge brute renseignee: {margin_rate * 100:.1f}%"
                )
            if not reasons:
                reasons.append("produit actif et disponible")
            scored.append(
                PromotionProductScore(
                    product_id=product_id,
                    name=product.name or f"Produit #{product_id}",
                    brand=product.brand,
                    category=product.category,
                    price=round(float(product.price or 0), 2),
                    currency=product.currency,
                    stock=product.stock,
                    score=score,
                    reasons=reasons,
                )
            )
        return sorted(
            scored,
            key=lambda item: (item.score, item.stock),
            reverse=True,
        )

    @staticmethod
    def _select_pack(
        scored: list[PromotionProductScore],
        pairs: list[dict[str, int]],
    ) -> list[PromotionProductScore]:
        if len(scored) < 2:
            return scored
        pair_counts: dict[frozenset[int], int] = {
            frozenset(
                (
                    item["left_product_id"],
                    item["right_product_id"],
                )
            ): item["order_count"]
            for item in pairs
        }
        max_pair_count = max(pair_counts.values(), default=1)
        selected = [scored[0]]
        candidates = scored[1:80]
        while candidates and len(selected) < 3:
            best = max(
                candidates,
                key=lambda candidate: (
                    candidate.score * 0.6
                    + max(
                        (
                            pair_counts.get(
                                frozenset(
                                    (candidate.product_id, current.product_id)
                                ),
                                0,
                            )
                            / max_pair_count
                            * 30
                            for current in selected
                        ),
                        default=0,
                    )
                    + (
                        10
                        if candidate.category
                        and all(
                            candidate.category != current.category
                            for current in selected
                        )
                        else 0
                    )
                ),
            )
            pair_reason = max(
                (
                    pair_counts.get(
                        frozenset((best.product_id, current.product_id)),
                        0,
                    )
                    for current in selected
                ),
                default=0,
            )
            if pair_reason:
                best.reasons.append(
                    f"achete avec un produit du pack dans {pair_reason} commande(s)"
                )
            elif best.category and all(
                best.category != current.category for current in selected
            ):
                best.reasons.append("categorie complementaire dans le pack")
            selected.append(best)
            candidates.remove(best)
        return selected
