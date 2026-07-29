from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.product import ProductResponse


CampaignType = Literal[
    "product_launch",
    "promotion",
    "awareness",
    "retention",
]
MarketingTone = Literal["premium", "energetic", "educational", "direct"]
MarketingChannel = Literal["instagram", "facebook", "email", "whatsapp"]
PromotionKind = Literal["single_product", "pack"]
PromotionSelectionMode = Literal["automatic", "manual"]


class PromotionProductScore(BaseModel):
    product_id: int
    name: str
    brand: str | None = None
    category: str | None = None
    price: float
    currency: str = "MAD"
    stock: int
    score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class PromotionSuggestionRequest(BaseModel):
    promotion_kind: PromotionKind
    product_ids: list[int] = Field(default_factory=list, max_length=4)

    @field_validator("product_ids")
    @classmethod
    def unique_product_ids(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


class PromotionSuggestionResponse(BaseModel):
    promotion_kind: PromotionKind
    products: list[PromotionProductScore]
    regular_total: float
    suggested_discount_percentage: float
    suggested_price: float
    currency: str = "MAD"
    data_notes: list[str] = Field(default_factory=list)


class ActivePromotionResponse(BaseModel):
    id: int
    promotion_kind: str
    title: str
    headline: str
    message: str
    cta_label: str
    products: list[ProductResponse]
    regular_total: float
    discount_percentage: float
    promotional_total: float
    currency: str
    starts_at: datetime | None
    ends_at: datetime | None


class MarketingGenerateRequest(BaseModel):
    campaign_type: CampaignType
    topic: str = Field(min_length=3, max_length=300)
    objective: str = Field(min_length=3, max_length=500)
    audience: str = Field(
        default="sportifs au Maroc",
        min_length=3,
        max_length=160,
    )
    tone: MarketingTone = "premium"
    channels: list[MarketingChannel] = Field(min_length=1, max_length=4)
    product_id: int | None = Field(default=None, ge=1)
    promotion_kind: PromotionKind | None = None
    selection_mode: PromotionSelectionMode | None = None
    product_ids: list[int] = Field(default_factory=list, max_length=4)
    discount_percentage: float | None = Field(default=None, ge=0, le=50)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    offer_details: str | None = Field(default=None, max_length=500)

    @field_validator("channels")
    @classmethod
    def unique_channels(
        cls,
        value: list[MarketingChannel],
    ) -> list[MarketingChannel]:
        return list(dict.fromkeys(value))

    @field_validator("product_ids")
    @classmethod
    def unique_products(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_promotion_selection(self) -> "MarketingGenerateRequest":
        if self.product_id and not self.product_ids:
            self.product_ids = [self.product_id]
        if self.campaign_type != "promotion":
            return self
        self.promotion_kind = self.promotion_kind or "single_product"
        self.selection_mode = self.selection_mode or "automatic"
        if self.selection_mode == "manual":
            expected_min = 2 if self.promotion_kind == "pack" else 1
            expected_max = 4 if self.promotion_kind == "pack" else 1
            if not expected_min <= len(self.product_ids) <= expected_max:
                raise ValueError(
                    "Manual single-product promotions need one product; "
                    "manual packs need two to four products"
                )
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("Promotion end date must be after start date")
        return self


class MarketingGeneratedFields(BaseModel):
    campaign_title: str = Field(min_length=5, max_length=180)
    headline: str = Field(min_length=5, max_length=220)
    core_message: str = Field(min_length=30, max_length=3000)
    email_subject: str | None = Field(default=None, max_length=180)
    email_body: str | None = Field(default=None, max_length=5000)
    whatsapp_message: str | None = Field(default=None, max_length=1500)
    social_caption: str | None = Field(default=None, max_length=2200)
    cta_label: str = Field(min_length=2, max_length=80)
    hashtags: list[str] = Field(default_factory=list, max_length=12)
    recommended_schedule: str | None = Field(default=None, max_length=300)


class MarketingCampaignUpdate(BaseModel):
    audience: str | None = Field(default=None, min_length=3, max_length=160)
    channels: list[MarketingChannel] | None = Field(
        default=None,
        min_length=1,
        max_length=4,
    )
    campaign_title: str | None = Field(default=None, min_length=5, max_length=180)
    headline: str | None = Field(default=None, min_length=5, max_length=220)
    core_message: str | None = Field(default=None, min_length=30, max_length=3000)
    email_subject: str | None = Field(default=None, max_length=180)
    email_body: str | None = Field(default=None, max_length=5000)
    whatsapp_message: str | None = Field(default=None, max_length=1500)
    social_caption: str | None = Field(default=None, max_length=2200)
    cta_label: str | None = Field(default=None, min_length=2, max_length=80)
    hashtags: list[str] | None = Field(default=None, max_length=12)
    recommended_schedule: str | None = Field(default=None, max_length=300)
    promotion_kind: PromotionKind | None = None
    selection_mode: PromotionSelectionMode | None = None
    product_ids: list[int] | None = Field(default=None, max_length=4)
    discount_percentage: float | None = Field(default=None, ge=0, le=50)
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("channels")
    @classmethod
    def unique_channels(
        cls,
        value: list[MarketingChannel] | None,
    ) -> list[MarketingChannel] | None:
        return list(dict.fromkeys(value)) if value else value

    @field_validator("product_ids")
    @classmethod
    def unique_updated_products(
        cls,
        value: list[int] | None,
    ) -> list[int] | None:
        return list(dict.fromkeys(value)) if value else value


class MarketingCampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_type: str
    topic: str
    objective: str
    audience: str
    tone: str
    channels: list[str]
    product_id: int | None
    promotion_kind: str | None
    selection_mode: str | None
    product_ids: list[int]
    selection_scores: list[dict]
    discount_percentage: float | None
    starts_at: datetime | None
    ends_at: datetime | None
    offer_details: str | None
    campaign_title: str
    headline: str
    core_message: str
    email_subject: str | None
    email_body: str | None
    whatsapp_message: str | None
    social_caption: str | None
    cta_label: str
    hashtags: list[str]
    recommended_schedule: str | None
    status: str
    model: str
    created_by: int
    approved_by: int | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MarketingCampaignListResponse(BaseModel):
    items: list[MarketingCampaignResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
