from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.analytics import AnalyticsReport
from app.services.analytics_agent import AnalyticsAgentService


router = APIRouter(prefix="/admin/ai/analytics", tags=["AI Analytics"])


@router.get("/report", response_model=AnalyticsReport)
async def analytics_report(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    period_days: Annotated[int, Query(ge=7, le=90)] = 30,
    use_ai: bool = False,
) -> AnalyticsReport:
    return await AnalyticsAgentService(session).report(
        period_days,
        use_ai=use_ai,
    )
