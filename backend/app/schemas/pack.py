from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.product import ProductResponse


class PackItemInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=20)


class PackCreate(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    description: str = Field(default="", max_length=5000)
    highlights: list[str] = Field(default_factory=list, max_length=12)
    items: list[PackItemInput] = Field(min_length=2, max_length=20)
    discount_percentage: float = Field(default=0, ge=0, le=90)
    promotional_price: float | None = Field(default=None, gt=0)
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def validate_pack(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Un produit ne peut apparaitre qu'une fois dans le pack")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("La date de fin doit etre apres la date de debut")
        return self


class PackUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    highlights: list[str] | None = Field(default=None, max_length=12)
    items: list[PackItemInput] | None = Field(default=None, min_length=2, max_length=20)
    discount_percentage: float | None = Field(default=None, ge=0, le=90)
    promotional_price: float | None = Field(default=None, gt=0)
    is_active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def validate_pack(self):
        if self.items is not None:
            ids = [item.product_id for item in self.items]
            if len(ids) != len(set(ids)):
                raise ValueError("Un produit ne peut apparaitre qu'une fois dans le pack")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("La date de fin doit etre apres la date de debut")
        return self


class PackProductResponse(BaseModel):
    product: ProductResponse
    quantity: int


class PackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str
    highlights: list[str]
    main_image_url: str | None
    gallery: list[str]
    products: list[PackProductResponse]
    regular_price: float
    discount_percentage: float
    promotional_price: float
    currency: str
    stock: int
    is_available: bool
    is_active: bool
    source: str
    campaign_id: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PackListResponse(BaseModel):
    items: list[PackResponse]
    total: int
