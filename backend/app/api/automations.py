import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.sqlite import get_sqlite_session
from app.schemas.automation import (
    AutomationRunResponse,
    OutboxCompleteRequest,
    OutboxCompleteResponse,
    OutboxItemResponse,
)
from app.services.automation import AutomationService


router = APIRouter(prefix="/automations", tags=["n8n Automations"])


def require_automation_key(
    value: Annotated[str | None, Header(alias="X-Automation-Key")] = None,
) -> None:
    if value is None or not hmac.compare_digest(
        value,
        settings.automation_api_key,
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Clé d'automatisation invalide",
        )


@router.post(
    "/delivery/scan",
    response_model=AutomationRunResponse,
    dependencies=[Depends(require_automation_key)],
)
async def automated_delivery_scan(
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> AutomationRunResponse:
    return await AutomationService(session).scan_delivery()


@router.post(
    "/carts/abandoned",
    response_model=AutomationRunResponse,
    dependencies=[Depends(require_automation_key)],
)
async def abandoned_cart_scan(
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    older_than_hours: Annotated[int, Query(ge=12, le=168)] = 24,
) -> AutomationRunResponse:
    return await AutomationService(session).scan_abandoned_carts(
        older_than_hours=older_than_hours
    )


@router.get(
    "/outbox",
    response_model=list[OutboxItemResponse],
    dependencies=[Depends(require_automation_key)],
)
async def pending_outbox(
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[OutboxItemResponse]:
    return await AutomationService(session).pending_outbox(limit)


@router.post(
    "/outbox/{item_id}/complete",
    response_model=OutboxCompleteResponse,
    dependencies=[Depends(require_automation_key)],
)
async def complete_outbox(
    item_id: int,
    data: OutboxCompleteRequest,
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OutboxCompleteResponse:
    return await AutomationService(session).complete_outbox(
        item_id,
        success=data.success,
        error=data.error,
    )
