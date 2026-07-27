from __future__ import annotations

import json
import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.ai_infrastructure import get_ai_http_client
from app.repositories.product import ProductRepository
from app.repositories.stock_forecast import StockForecastRepository
from app.schemas.stock_forecast import (
    StockForecastItem,
    StockForecastReport,
    StockForecastSummary,
)


logger = logging.getLogger("nutrifit.stock_forecast_agent")

OLLAMA_STOCK_FORECAST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "analysis": {"type": "string"},
        "insights": {"type": "array", "items": {"type": "string"}},
        "alerts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["analysis", "insights", "alerts"],
    "additionalProperties": False,
}

RISK_PRIORITY = {
    "out_of_stock": 0,
    "critical": 1,
    "warning": 2,
    "healthy": 3,
    "dormant": 4,
}


class StockForecastAgentService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        repository: StockForecastRepository | None = None,
        product_repository: ProductRepository | None = None,
    ) -> None:
        self.repository = repository or StockForecastRepository(session)
        self.product_repository = product_repository or ProductRepository()

    async def report(
        self,
        lookback_days: int,
        *,
        target_cover_days: int = 30,
        use_ai: bool = True,
    ) -> StockForecastReport:
        end = datetime.now(UTC)
        start = end - timedelta(days=lookback_days)
        previous_start = start - timedelta(days=lookback_days)
        current_sales = await self.repository.product_sales(start, end)
        previous_sales = await self.repository.product_sales(
            previous_start,
            start,
        )
        products, _ = await self.product_repository.list_products(
            skip=0,
            limit=1000,
            sort_by="stock_desc",
            active_only=True,
        )

        items = [
            self._forecast_product(
                product,
                current_sales.get(int(product["product_id"]), 0),
                previous_sales.get(int(product["product_id"]), 0),
                lookback_days=lookback_days,
                target_cover_days=target_cover_days,
                generated_at=end,
            )
            for product in products
        ]
        items.sort(
            key=lambda item: (
                RISK_PRIORITY[item.risk],
                item.days_remaining if item.days_remaining is not None else 10**9,
                -item.average_daily_sales,
                item.name.lower(),
            )
        )
        summary = StockForecastSummary(
            products=len(items),
            out_of_stock=sum(item.risk == "out_of_stock" for item in items),
            critical=sum(item.risk == "critical" for item in items),
            warning=sum(item.risk == "warning" for item in items),
            healthy=sum(item.risk == "healthy" for item in items),
            dormant=sum(item.risk == "dormant" for item in items),
            recommended_reorder_units=sum(
                item.recommended_reorder_quantity for item in items
            ),
        )
        analysis, insights, alerts = self._local_analysis(
            lookback_days,
            summary,
            items,
        )
        model = "prévision locale"

        if use_ai:
            generated = await self._generate_ai_analysis(
                lookback_days,
                target_cover_days,
                summary,
                items,
            )
            if generated is not None:
                analysis, insights, ai_alerts = generated
                alerts = list(dict.fromkeys([*alerts, *ai_alerts]))[:8]
                model = settings.ollama_chat_model

        return StockForecastReport(
            lookback_days=lookback_days,
            target_cover_days=target_cover_days,
            generated_at=end,
            summary=summary,
            items=items,
            analysis=analysis,
            insights=insights[:8],
            alerts=alerts[:8],
            model=model,
            read_only=True,
        )

    @staticmethod
    def _forecast_product(
        product: dict[str, Any],
        units_sold: int,
        previous_units_sold: int,
        *,
        lookback_days: int,
        target_cover_days: int,
        generated_at: datetime,
    ) -> StockForecastItem:
        stock = max(int(product.get("stock") or 0), 0)
        average_daily_sales = round(units_sold / lookback_days, 3)
        if previous_units_sold == 0:
            trend = 100.0 if units_sold > 0 else 0.0
        else:
            trend = round(
                ((units_sold - previous_units_sold) / previous_units_sold) * 100,
                1,
            )

        days_remaining: float | None = None
        stockout_date = None
        if average_daily_sales > 0:
            days_remaining = round(stock / average_daily_sales, 1)
            stockout_date = (
                generated_at + timedelta(days=math.ceil(days_remaining))
            ).date()

        target_units = math.ceil(average_daily_sales * target_cover_days)
        reorder_quantity = max(target_units - stock, 0)
        if stock == 0:
            risk = "out_of_stock"
        elif average_daily_sales == 0:
            risk = "dormant"
        elif days_remaining is not None and days_remaining <= 7:
            risk = "critical"
        elif days_remaining is not None and days_remaining <= 21:
            risk = "warning"
        else:
            risk = "healthy"

        return StockForecastItem(
            product_id=int(product["product_id"]),
            name=str(product.get("name") or "Produit"),
            brand=product.get("brand"),
            stock=stock,
            price=(
                float(product["price"])
                if product.get("price") is not None
                else None
            ),
            units_sold=units_sold,
            previous_units_sold=previous_units_sold,
            sales_trend_pct=trend,
            average_daily_sales=average_daily_sales,
            days_remaining=days_remaining,
            predicted_stockout_date=stockout_date,
            recommended_reorder_quantity=reorder_quantity,
            risk=risk,
        )

    @staticmethod
    def _local_analysis(
        lookback_days: int,
        summary: StockForecastSummary,
        items: list[StockForecastItem],
    ) -> tuple[str, list[str], list[str]]:
        analysis = (
            f"Sur la base des ventes des {lookback_days} derniers jours, "
            f"{summary.out_of_stock + summary.critical} produit(s) demandent "
            "une attention immédiate."
        )
        insights = [
            (
                f"{summary.healthy} produit(s) disposent d'une couverture "
                "de stock confortable."
            ),
            (
                f"{summary.dormant} produit(s) n'ont enregistré aucune vente "
                "sur la période analysée."
            ),
        ]
        fastest = next(
            (item for item in items if item.average_daily_sales > 0),
            None,
        )
        if fastest is not None:
            insights.append(
                f"{fastest.name} présente la couverture la plus urgente parmi "
                "les produits actuellement vendus."
            )

        alerts: list[str] = []
        if summary.out_of_stock:
            alerts.append(
                f"{summary.out_of_stock} produit(s) actif(s) sont en rupture."
            )
        if summary.critical:
            alerts.append(
                f"{summary.critical} produit(s) risquent une rupture sous 7 jours."
            )
        if summary.warning:
            alerts.append(
                f"{summary.warning} produit(s) ont moins de 21 jours de couverture."
            )
        return analysis, insights, alerts

    async def _generate_ai_analysis(
        self,
        lookback_days: int,
        target_cover_days: int,
        summary: StockForecastSummary,
        items: list[StockForecastItem],
    ) -> tuple[str, list[str], list[str]] | None:
        payload = {
            "lookback_days": lookback_days,
            "target_cover_days": target_cover_days,
            "summary": summary.model_dump(mode="json"),
            "priority_products": [
                item.model_dump(mode="json") for item in items[:20]
            ],
        }
        prompt = (
            "Tu es Stock Forecast Agent de NUTRIFIT. Analyse uniquement les "
            "chiffres fournis. Réponds en français. N'invente aucune vente, "
            "date ou quantité. Propose des priorités, mais ne prétends jamais "
            "avoir modifié le stock ou passé une commande fournisseur. Retourne "
            "uniquement un JSON avec analysis, insights et alerts.\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        try:
            response = await get_ai_http_client().post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_chat_model,
                    "prompt": prompt,
                    "format": OLLAMA_STOCK_FORECAST_SCHEMA,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 700},
                },
                timeout=60,
            )
            response.raise_for_status()
            data = json.loads(str(response.json().get("response") or ""))
            if not isinstance(data, dict):
                return None
            analysis = str(data.get("analysis") or "").strip()[:1200]
            if not analysis:
                return None
            return (
                analysis,
                self._clean_list(data.get("insights")),
                self._clean_list(data.get("alerts")),
            )
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Stock Forecast Agent AI summary unavailable: %s", exc)
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
