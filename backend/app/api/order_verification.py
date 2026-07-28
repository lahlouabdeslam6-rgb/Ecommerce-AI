from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.order_verification import OrderVerificationReport
from app.services.order_verification_agent import OrderVerificationAgentService


router = APIRouter(
    prefix="/ai/order-verification",
    tags=["AI Order Verification"],
)


@router.get("/report", response_model=OrderVerificationReport)
async def order_verification_report(
    _: Annotated[User, Depends(require_roles("admin", "support"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OrderVerificationReport:
    return await OrderVerificationAgentService(session).report()
