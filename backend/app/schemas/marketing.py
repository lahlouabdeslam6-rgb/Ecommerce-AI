from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


CampaignType = Literal[
    "product_launch",
    "promotion",
    "awareness",
    "retention",
]
MarketingTone = Literal["premium", "energetic", "educational", "direct"]
MarketingChannel = Literal["instagram", "facebook", "email", "whatsapp"]


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
    offer_details: str | None = Field(default=None, max_length=500)

    @field_validator("channels")
    @classmethod
    def unique_channels(
        cls,
        value: list[MarketingChannel],
    ) -> list[MarketingChannel]:
        return list(dict.fromkeys(value))


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

    @field_validator("channels")
    @classmethod
    def unique_channels(
        cls,
        value: list[MarketingChannel] | None,
    ) -> list[MarketingChannel] | None:
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
