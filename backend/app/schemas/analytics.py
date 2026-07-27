from datetime import date, datetime

from pydantic import BaseModel, Field


class AnalyticsMetrics(BaseModel):
    orders: int
    paid_orders: int
    delivered_orders: int
    cancelled_orders: int
    units_sold: int
    revenue_mad: float
    average_order_value_mad: float


class AnalyticsComparison(BaseModel):
    orders_change_pct: float
    revenue_change_pct: float
    units_change_pct: float


class AnalyticsDailyPoint(BaseModel):
    date: date
    orders: int
    revenue_mad: float


class AnalyticsTopProduct(BaseModel):
    product_id: int
    name: str
    brand: str | None = None
    quantity: int
    revenue_mad: float


class AnalyticsUnsoldProduct(BaseModel):
    product_id: int
    name: str
    brand: str | None = None
    stock: int
    price: float | None = None


class AnalyticsReport(BaseModel):
    period_days: int = Field(ge=7, le=90)
    generated_at: datetime
    current: AnalyticsMetrics
    previous: AnalyticsMetrics
    comparison: AnalyticsComparison
    daily_sales: list[AnalyticsDailyPoint]
    top_products: list[AnalyticsTopProduct]
    unsold_products: list[AnalyticsUnsoldProduct]
    summary: str
    insights: list[str]
    alerts: list[str]
    model: str
    read_only: bool = True
