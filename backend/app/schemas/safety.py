from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SafetySource = Literal[
    "manual",
    "product_suggestion",
    "content",
    "marketing_campaign",
    "support_reply",
]


class SafetyReviewRequest(BaseModel):
    text: str = Field(min_length=3, max_length=12000)
    source_type: SafetySource = "manual"
    source_id: str | None = Field(default=None, max_length=80)
    action: str = Field(default="manual.review", min_length=3, max_length=80)


class SafetyAIResult(BaseModel):
    status: Literal["safe", "warning", "blocked"]
    risk_level: Literal["low", "medium", "high"]
    reasons: list[str] = Field(default_factory=list, max_length=10)
    recommendations: list[str] = Field(default_factory=list, max_length=10)
    confidence: float = Field(ge=0, le=1)


class SafetyReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    source_id: str | None
    action: str
    status: str
    risk_level: str
    reasons: list[str]
    recommendations: list[str]
    matched_rules: list[str]
    excerpt: str
    model: str
    actor_id: int | None
    created_at: datetime


class SafetyReviewListResponse(BaseModel):
    items: list[SafetyReviewResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
