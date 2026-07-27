from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


DeliveryRisk = Literal["normal", "warning", "critical", "failed"]


class DeliveryOrderItem(BaseModel):
    order_id: int
    user_id: int
    customer_name: str
    customer_email: str
    phone: str
    city: str
    order_status: str
    created_at: datetime
    age_hours: float
    estimated_delivery_date: date | None
    risk: DeliveryRisk
    reason: str
    total: float
    currency: str


class DeliverySummary(BaseModel):
    active_orders: int
    normal: int
    warning: int
    critical: int
    failed: int
    alerts_sent: int = 0


class DeliveryReport(BaseModel):
    generated_at: datetime
    summary: DeliverySummary
    items: list[DeliveryOrderItem]
    analysis: str
    model: str = "règles de livraison NUTRIFIT"
    read_only: bool = True
