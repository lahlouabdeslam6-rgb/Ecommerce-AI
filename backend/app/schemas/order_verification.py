from datetime import datetime
from typing import Literal

from pydantic import BaseModel


VerificationStatus = Literal[
    "to_confirm",
    "priority_review",
    "possible_duplicate",
    "ready_to_prepare",
]


class OrderVerificationItem(BaseModel):
    order_id: int
    user_id: int | None
    customer_name: str
    customer_email: str
    phone: str
    address: str
    city: str
    total: float
    currency: str
    payment_method: str
    created_at: datetime
    verification_status: VerificationStatus
    priority_score: int
    signals: list[str]
    recommended_action: str


class OrderVerificationSummary(BaseModel):
    orders_to_review: int
    to_confirm: int
    priority_review: int
    possible_duplicate: int
    ready_to_prepare: int


class OrderVerificationReport(BaseModel):
    generated_at: datetime
    summary: OrderVerificationSummary
    items: list[OrderVerificationItem]
    analysis: str
    model: str = "règles de vérification NUTRIFIT"
    read_only: bool = True
    automatic_rejection: bool = False
