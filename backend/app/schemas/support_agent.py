from typing import Literal

from pydantic import BaseModel, Field


SupportTopic = Literal[
    "order",
    "delivery",
    "payment",
    "return",
    "product",
    "medical_safety",
    "general",
]


class SupportAgentRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1000)
    order_id: int | None = Field(default=None, ge=1)
    product_id: int | None = Field(default=None, ge=1)


class SupportOrderContext(BaseModel):
    order_id: int
    order_status: str
    order_status_label: str
    payment_method: str
    payment_status: str
    total: float
    currency: str


class SupportProductContext(BaseModel):
    product_id: int
    name: str
    brand: str | None = None
    category: str | None = None
    price: float | None = None
    currency: str = "MAD"
    stock: int
    ingredients: list[str] = Field(default_factory=list)


class SupportAgentResponse(BaseModel):
    topic: SupportTopic
    answer: str
    needs_human: bool
    order: SupportOrderContext | None = None
    product: SupportProductContext | None = None
    suggested_questions: list[str] = Field(default_factory=list)
    safety_notice: str | None = None
    support_url: str = "/help"
    ticket_id: int | None = None
    ticket_created: bool = False
    handoff_message: str | None = None
    model: str
    read_only: bool = True
