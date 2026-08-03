from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class CheckoutRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30)
    city: str = Field(min_length=2, max_length=120)
    address: str | None = Field(default=None, min_length=5, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    payment_method: str = Field(default="cash_on_delivery", pattern=r"^(cash_on_delivery|card)$")
    card_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    card_brand: str | None = Field(default=None, max_length=30)
    payment_token: str | None = Field(default=None, min_length=8, max_length=200)


class GuestCartItemInput(BaseModel):
    product_id: int | None = Field(default=None, gt=0)
    pack_id: int | None = Field(default=None, gt=0)
    quantity: int = Field(ge=1, le=99)

    @model_validator(mode="after")
    def one_item_type(self):
        if (self.product_id is None) == (self.pack_id is None):
            raise ValueError("Indique un produit ou un pack")
        if self.pack_id is not None and self.quantity > 20:
            raise ValueError("Maximum 20 packs par ligne")
        return self


class GuestCheckoutRequest(CheckoutRequest):
    email: EmailStr | None = None
    items: list[GuestCartItemInput] = Field(min_length=1, max_length=50)


class GuestOrderTrackRequest(BaseModel):
    order_id: int = Field(gt=0)
    tracking_token: str = Field(min_length=32, max_length=200)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    pack_id: int | None = None
    item_type: str = "product"
    product_name: str
    brand: str | None
    image_url: str | None
    unit_price: float
    quantity: int
    subtotal: float


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    email: str
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


class GuestCheckoutResponse(BaseModel):
    order: OrderResponse
    tracking_token: str


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
