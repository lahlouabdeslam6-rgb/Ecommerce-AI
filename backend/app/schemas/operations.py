from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    actor_email: str | None = None
    actor_role: str
    action: str
    entity_type: str
    entity_id: str | None
    details: str | None
    created_at: datetime


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    movement_type: str
    quantity: int
    stock_before: int
    stock_after: int
    reference_type: str | None
    reference_id: str | None
    actor_id: int | None
    note: str | None
    created_at: datetime


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    target_role: str | None
    notification_type: str
    title: str
    message: str
    link: str | None
    is_read: bool
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int


class StockMovementListResponse(BaseModel):
    items: list[StockMovementResponse]
    total: int


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread: int
