from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


StockRisk = Literal[
    "out_of_stock",
    "critical",
    "warning",
    "healthy",
    "dormant",
]


class StockForecastItem(BaseModel):
    product_id: int
    name: str
    brand: str | None = None
    stock: int
    price: float | None = None
    units_sold: int
    previous_units_sold: int
    sales_trend_pct: float
    average_daily_sales: float
    days_remaining: float | None = None
    predicted_stockout_date: date | None = None
    recommended_reorder_quantity: int
    risk: StockRisk


class StockForecastSummary(BaseModel):
    products: int
    out_of_stock: int
    critical: int
    warning: int
    healthy: int
    dormant: int
    recommended_reorder_units: int


class StockForecastReport(BaseModel):
    lookback_days: int = Field(ge=14, le=90)
    target_cover_days: int = Field(ge=7, le=90)
    generated_at: datetime
    summary: StockForecastSummary
    items: list[StockForecastItem]
    analysis: str
    insights: list[str]
    alerts: list[str]
    model: str
    read_only: bool = True
