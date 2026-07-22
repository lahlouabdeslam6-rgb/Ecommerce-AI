from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.operations import OperationsRepository
from app.schemas.operations import (
    AuditLogListResponse,
    AuditLogResponse,
    NotificationListResponse,
    NotificationResponse,
    StockMovementListResponse,
    StockMovementResponse,
)


router = APIRouter(tags=["Operations"])


@router.get("/admin/audit-logs", response_model=AuditLogListResponse)
async def audit_logs(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditLogListResponse:
    rows, total = await OperationsRepository(session).list_audit(page, page_size)
    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=item.id,
                actor_id=item.actor_id,
                actor_email=actor_email,
                actor_role=item.actor_role,
                action=item.action,
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                details=item.details,
                created_at=item.created_at,
            )
            for item, actor_email in rows
        ],
        total=total,
    )


@router.get("/stock-movements", response_model=StockMovementListResponse)
async def stock_movements(
    _: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    product_id: int | None = None,
) -> StockMovementListResponse:
    items, total = await OperationsRepository(session).list_stock(
        page, page_size, product_id
    )
    return StockMovementListResponse(
        items=[StockMovementResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/notifications", response_model=NotificationListResponse)
async def notifications(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> NotificationListResponse:
    items, unread = await OperationsRepository(session).list_notifications(
        user_id=user.id, role=user.role
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(item) for item in items],
        unread=unread,
    )


@router.patch("/notifications/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> None:
    if not await OperationsRepository(session).mark_read(
        notification_id, user.id, user.role
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
