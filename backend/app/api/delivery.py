from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.delivery import DeliveryReport
from app.services.delivery_agent import DeliveryAgentService


router = APIRouter(prefix="/admin/ai/delivery", tags=["AI Delivery"])


@router.get("/report", response_model=DeliveryReport)
async def delivery_report(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> DeliveryReport:
    return await DeliveryAgentService(session).report(notify=False)


@router.post("/scan", response_model=DeliveryReport)
async def delivery_scan(
    user: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> DeliveryReport:
    return await DeliveryAgentService(session).report(
        notify=True,
        actor=user,
    )

