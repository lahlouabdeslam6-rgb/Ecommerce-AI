from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.content import ContentType, ContentTone
from app.schemas.marketing import CampaignType, MarketingTone, MarketingChannel


class OrchestratorTaskType(str, Enum):
    product = "product"
    recommendation = "recommendation"
    support = "support"
    content = "content"
    marketing = "marketing"
    analytics = "analytics"
    stock_forecast = "stock_forecast"
    delivery = "delivery"
    seo = "seo"
    order_verification = "order_verification"


ALLOWED_CONTEXT_KEYS = {
    "product_id",
    "order_id",
    "objective",
    "max_price",
    "limit",
    "content_type",
    "topic",
    "audience",
    "tone",
    "language",
    "campaign_type",
    "channels",
    "offer_details",
    "period_days",
    "lookback_days",
}


class OrchestratorContext(BaseModel):
    product_id: int | None = Field(None, gt=0)
    order_id: int | None = Field(None, gt=0)
    objective: str | None = Field(None, min_length=2, max_length=500)
    max_price: float | None = Field(None, gt=0, le=100_000)
    limit: int | None = Field(None, ge=1, le=8)
    
    content_type: ContentType | None = Field(None)
    topic: str | None = Field(None, min_length=3, max_length=300)
    audience: str | None = Field(None, min_length=3, max_length=160)
    tone: ContentTone | MarketingTone | None = Field(None)
    language: Literal["fr"] | None = Field(None)
    
    campaign_type: CampaignType | None = Field(None)
    channels: list[MarketingChannel] | None = Field(None, min_length=1, max_length=4)
    offer_details: str | None = Field(None, max_length=500)
    period_days: int | None = Field(None, ge=7, le=90)
    lookback_days: int | None = Field(None, ge=14, le=90)

    @model_validator(mode="before")
    @classmethod
    def reject_unknown_keys(cls, values: Any) -> Any:
        if isinstance(values, dict):
            unknown = set(values.keys()) - ALLOWED_CONTEXT_KEYS
            if unknown:
                raise ValueError(
                    f"Unknown context fields: {', '.join(sorted(unknown))}"
                )
        return values


class OrchestratorRequest(BaseModel):
    message: str = Field(
        ..., description="Natural language user request", min_length=1, max_length=500
    )
    task_type: OrchestratorTaskType | None = Field(
        None, description="Explicit agent override"
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        return v
    context: OrchestratorContext | None = Field(
        None,
        description="Optional structured context required by the chosen agent",
    )
    confirm_action: bool = Field(
        False,
        description="When true, indicates user approved a mutating action "
        "(not executed in this version)",
    )


class AgentResult(BaseModel):
    agent: str
    status: str = "success"
    data: dict[str, Any] = Field(default_factory=dict)


class OrchestratorResponse(BaseModel):
    detected_intent: str = Field(
        ..., description="Detected intent or chosen agent"
    )
    selected_agents: list[str] = Field(
        ..., description="List of agents that handled the request"
    )
    results: list[AgentResult] = Field(
        ..., description="Per-agent structured results"
    )
    requires_confirmation: bool = Field(
        ..., description="Whether the request involves a mutation"
    )
    proposed_action: str | None = Field(
        None,
        description="Description of the proposed mutation action",
    )


class OrchestratorHistoryItem(BaseModel):
    id: int
    actor_id: int | None
    actor_email: str | None = None
    actor_role: str
    message: str
    detected_intent: str
    selected_agents: list[str]
    results: list[AgentResult]
    requires_confirmation: bool
    proposed_action: str | None = None
    created_at: datetime


class OrchestratorHistoryListResponse(BaseModel):
    items: list[OrchestratorHistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int
