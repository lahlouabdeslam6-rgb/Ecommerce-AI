from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.ai_infrastructure import get_ai_http_client
from app.repositories.analytics import AnalyticsRepository
from app.repositories.product import ProductRepository
from app.schemas.analytics import (
    AnalyticsComparison,
    AnalyticsDailyPoint,
    AnalyticsMetrics,
    AnalyticsReport,
    AnalyticsTopProduct,
    AnalyticsUnsoldProduct,
)


logger = logging.getLogger("nutrifit.analytics_agent")

OLLAMA_ANALYTICS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "insights": {"type": "array", "items": {"type": "string"}},
        "alerts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "insights", "alerts"],
    "additionalProperties": False,
}


class AnalyticsAgentService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        repository: AnalyticsRepository | None = None,
        product_repository: ProductRepository | None = None,
    ) -> None:
        self.repository = repository or AnalyticsRepository(session)
        self.product_repository = product_repository or ProductRepository()

    async def report(
        self,
        period_days: int,
        *,
        use_ai: bool = True,
    ) -> AnalyticsReport:
        end = datetime.now(UTC)
        start = end - timedelta(days=period_days)
        previous_start = start - timedelta(days=period_days)

        current_data = await self.repository.metrics(start, end)
        previous_data = await self.repository.metrics(previous_start, start)
        daily_data = await self.repository.daily_sales(start, end)
        top_data = await self.repository.top_products(start, end)
        sold_ids = await self.repository.sold_product_ids(start, end)
        current = AnalyticsMetrics.model_validate(current_data)
        previous = AnalyticsMetrics.model_validate(previous_data)
        comparison = AnalyticsComparison(
            orders_change_pct=self._change(
                current.orders,
                previous.orders,
            ),
            revenue_change_pct=self._change(
                current.revenue_mad,
                previous.revenue_mad,
            ),
            units_change_pct=self._change(
                current.units_sold,
                previous.units_sold,
            ),
        )
        daily_sales = self._complete_daily_series(
            end.date() - timedelta(days=period_days - 1),
            period_days,
            daily_data,
        )
        top_products = [
            AnalyticsTopProduct.model_validate(item) for item in top_data
        ]
        unsold_products = await self._unsold_products(sold_ids)
        summary, insights, alerts = self._local_analysis(
            period_days,
            current,
            comparison,
            top_products,
            unsold_products,
        )
        model = "analyse locale"

        if use_ai:
            generated = await self._generate_ai_analysis(
                period_days=period_days,
                current=current,
                previous=previous,
                comparison=comparison,
                top_products=top_products,
                unsold_products=unsold_products,
            )
            if generated is not None:
                summary, insights, ai_alerts = generated
                alerts = list(dict.fromkeys([*alerts, *ai_alerts]))[:8]
                model = settings.ollama_chat_model

        return AnalyticsReport(
            period_days=period_days,
            generated_at=end,
            current=current,
            previous=previous,
            comparison=comparison,
            daily_sales=daily_sales,
            top_products=top_products,
            unsold_products=unsold_products,
            summary=summary,
            insights=insights[:8],
            alerts=alerts[:8],
            model=model,
            read_only=True,
        )

    async def _unsold_products(
        self,
        sold_ids: set[int],
    ) -> list[AnalyticsUnsoldProduct]:
        products, _ = await self.product_repository.list_products(
            skip=0,
            limit=1000,
            sort_by="stock_desc",
            active_only=True,
        )
        result: list[AnalyticsUnsoldProduct] = []
        for product in products:
            product_id = int(product["product_id"])
            if product_id in sold_ids:
                continue
            result.append(
                AnalyticsUnsoldProduct(
                    product_id=product_id,
                    name=str(product.get("name") or "Produit"),
                    brand=product.get("brand"),
                    stock=int(product.get("stock") or 0),
                    price=(
                        float(product["price"])
                        if product.get("price") is not None
                        else None
                    ),
                )
            )
            if len(result) == 8:
                break
        return result

    @staticmethod
    def _complete_daily_series(
        start: date,
        period_days: int,
        values: list[dict[str, Any]],
    ) -> list[AnalyticsDailyPoint]:
        by_date = {str(item["date"]): item for item in values}
        result: list[AnalyticsDailyPoint] = []
        for offset in range(period_days):
            current_date = start + timedelta(days=offset)
            item = by_date.get(current_date.isoformat())
            result.append(
                AnalyticsDailyPoint(
                    date=current_date,
                    orders=int(item["orders"]) if item else 0,
                    revenue_mad=float(item["revenue_mad"]) if item else 0,
                )
            )
        return result

    @staticmethod
    def _change(current: float | int, previous: float | int) -> float:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((float(current) - float(previous)) / float(previous)) * 100, 1)

    @staticmethod
    def _local_analysis(
        period_days: int,
        current: AnalyticsMetrics,
        comparison: AnalyticsComparison,
        top_products: list[AnalyticsTopProduct],
        unsold_products: list[AnalyticsUnsoldProduct],
    ) -> tuple[str, list[str], list[str]]:
        summary = (
            f"Sur les {period_days} derniers jours, NUTRIFIT a enregistré "
            f"{current.orders} commande(s) pour un revenu confirmé de "
            f"{current.revenue_mad:.2f} MAD."
        )
        insights = [
            (
                f"Le revenu a évolué de {comparison.revenue_change_pct:+.1f}% "
                "par rapport à la période précédente."
            ),
            (
                f"Le panier moyen confirmé est de "
                f"{current.average_order_value_mad:.2f} MAD."
            ),
        ]
        if top_products:
            leader = top_products[0]
            insights.append(
                f"{leader.name} est le produit le plus vendu avec "
                f"{leader.quantity} unité(s)."
            )
        if unsold_products:
            insights.append(
                f"{len(unsold_products)} produit(s) en stock dans cette liste "
                "n'ont enregistré aucune vente sur la période."
            )

        alerts: list[str] = []
        if current.orders and current.cancelled_orders / current.orders >= 0.2:
            alerts.append(
                "Le taux d'annulation atteint au moins 20 % des commandes."
            )
        if comparison.revenue_change_pct <= -20:
            alerts.append(
                "Le revenu a baissé d'au moins 20 % par rapport à la période précédente."
            )
        if current.orders == 0:
            alerts.append("Aucune commande n'a été enregistrée sur la période.")
        return summary, insights, alerts

    async def _generate_ai_analysis(
        self,
        *,
        period_days: int,
        current: AnalyticsMetrics,
        previous: AnalyticsMetrics,
        comparison: AnalyticsComparison,
        top_products: list[AnalyticsTopProduct],
        unsold_products: list[AnalyticsUnsoldProduct],
    ) -> tuple[str, list[str], list[str]] | None:
        payload = {
            "period_days": period_days,
            "current": current.model_dump(mode="json"),
            "previous": previous.model_dump(mode="json"),
            "comparison": comparison.model_dump(mode="json"),
            "top_products": [
                item.model_dump(mode="json") for item in top_products
            ],
            "unsold_products": [
                item.model_dump(mode="json") for item in unsold_products
            ],
        }
        prompt = (
            "Tu es Analytics Agent de NUTRIFIT. Analyse uniquement les données "
            "e-commerce fournies. Réponds en français, sans inventer de chiffre, "
            "sans promesse médicale et sans demander de modifier automatiquement "
            "le catalogue. Donne un résumé court, des observations concrètes et "
            "des alertes seulement si elles sont justifiées. Retourne uniquement "
            "un JSON avec summary, insights et alerts.\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        try:
            response = await get_ai_http_client().post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_chat_model,
                    "prompt": prompt,
                    "format": OLLAMA_ANALYTICS_SCHEMA,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 700},
                },
                timeout=60,
            )
            response.raise_for_status()
            raw = str(response.json().get("response") or "")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            summary = str(data.get("summary") or "").strip()[:1200]
            insights = self._clean_list(data.get("insights"))
            alerts = self._clean_list(data.get("alerts"))
            if not summary:
                return None
            return summary, insights, alerts
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Analytics Agent AI summary unavailable: %s", exc)
            return None

    @staticmethod
    def _clean_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [
            str(item).strip()[:500]
            for item in value
            if str(item).strip()
        ][:8]
