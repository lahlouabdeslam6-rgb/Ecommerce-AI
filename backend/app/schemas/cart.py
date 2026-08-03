from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=99)


class PackCartItemAdd(BaseModel):
    pack_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=20)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CartItemResponse(BaseModel):
    item_type: str = "product"
    product_id: int | None = None
    pack_id: int | None = None
    name: str
    brand: str | None = None
    image_url: str | None = None
    unit_price: float
    currency: str
    quantity: int
    subtotal: float
    stock: int
    is_available: bool


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    item_count: int
    subtotal: float
    currency: str = "MAD"
