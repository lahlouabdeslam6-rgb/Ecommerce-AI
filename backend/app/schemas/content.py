from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ContentType = Literal[
    "homepage_hero",
    "promotion",
    "category",
    "faq",
    "social_post",
]
ContentTone = Literal["premium", "energetic", "educational", "direct"]


class ContentGenerateRequest(BaseModel):
    content_type: ContentType
    topic: str = Field(min_length=3, max_length=300)
    objective: str | None = Field(default=None, max_length=500)
    audience: str = Field(
        default="sportifs au Maroc",
        min_length=3,
        max_length=120,
    )
    tone: ContentTone = "premium"
    language: Literal["fr"] = "fr"
    product_id: int | None = Field(default=None, ge=1)


class ContentGeneratedFields(BaseModel):
    title: str = Field(min_length=5, max_length=180)
    subtitle: str | None = Field(default=None, max_length=300)
    body: str = Field(min_length=30, max_length=4000)
    cta_label: str | None = Field(default=None, max_length=80)
    hashtags: list[str] = Field(default_factory=list, max_length=12)


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=180)
    subtitle: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, min_length=30, max_length=4000)
    cta_label: str | None = Field(default=None, max_length=80)
    hashtags: list[str] | None = Field(default=None, max_length=12)


class ContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_type: str
    topic: str
    objective: str | None
    audience: str
    tone: str
    language: str
    product_id: int | None
    title: str
    subtitle: str | None
    body: str
    cta_label: str | None
    hashtags: list[str]
    status: str
    model: str
    created_by: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContentListResponse(BaseModel):
    items: list[ContentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
