from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.stock_forecast import StockForecastReport
from app.services.stock_forecast_agent import StockForecastAgentService


router = APIRouter(
    prefix="/admin/ai/stock-forecast",
    tags=["AI Stock Forecast"],
)


@router.get("/report", response_model=StockForecastReport)
async def stock_forecast_report(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    lookback_days: Annotated[int, Query(ge=14, le=90)] = 30,
    use_ai: bool = False,
) -> StockForecastReport:
    return await StockForecastAgentService(session).report(
        lookback_days,
        target_cover_days=30,
        use_ai=use_ai,
    )
