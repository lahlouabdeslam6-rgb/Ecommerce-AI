from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AutomationRunResponse(BaseModel):
    scanned: int
    notifications_created: int
    outbox_created: int


class OutboxItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    channel: str
    recipient: str
    subject: str | None
    body: str
    reference_type: str | None
    reference_id: str | None
    status: str
    attempts: int
    created_at: datetime


class OutboxCompleteRequest(BaseModel):
    success: bool
    error: str | None = Field(default=None, max_length=1000)


class OutboxCompleteResponse(BaseModel):
    id: int
    status: Literal["sent", "failed"]

