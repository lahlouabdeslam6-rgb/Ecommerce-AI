from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CheckoutRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)
    address: str = Field(min_length=5, max_length=500)
    city: str = Field(min_length=2, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    payment_method: str = Field(default="cash_on_delivery", pattern=r"^(cash_on_delivery|card)$")
    card_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    card_brand: str | None = Field(default=None, max_length=30)
    payment_token: str | None = Field(default=None, min_length=8, max_length=200)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    brand: str | None
    image_url: str | None
    unit_price: float
    quantity: int
    subtotal: float


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    order_status: str
    payment_method: str
    payment_status: str
    card_last4: str | None
    card_brand: str | None
    payment_reference: str | None
    full_name: str
    phone: str
    address: str
    city: str
    notes: str | None
    subtotal: float
    delivery_fee: float
    total: float
    currency: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class OrderStatusUpdate(BaseModel):
    order_status: str = Field(
        pattern=(
            r"^(pending|confirmed|preparing|shipped|delivered|cancelled|"
            r"delivery_failed)$"
        )
    )


class DashboardResponse(BaseModel):
    users: int
    products: int
    active_products: int
    low_stock_products: int
    orders: int
    pending_orders: int
    delivered_orders: int
    revenue_mad: float
