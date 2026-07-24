from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.safety import (
    SafetyReviewListResponse,
    SafetyReviewRequest,
    SafetyReviewResponse,
)
from app.services.safety_agent import SafetyAgentService


router = APIRouter(prefix="/admin/ai/safety", tags=["AI Safety"])


@router.get("/reviews", response_model=SafetyReviewListResponse)
async def list_safety_reviews(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    review_status: Annotated[str | None, Query(max_length=20)] = None,
    source_type: Annotated[str | None, Query(max_length=50)] = None,
) -> SafetyReviewListResponse:
    return await SafetyAgentService(session).list(
        page=page,
        page_size=page_size,
        review_status=review_status,
        source_type=source_type,
    )


@router.post("/review", response_model=SafetyReviewResponse)
async def review_text(
    data: SafetyReviewRequest,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> SafetyReviewResponse:
    report = await SafetyAgentService(session).review(
        data.text,
        source_type=data.source_type,
        source_id=data.source_id,
        action=data.action,
        actor_id=admin.id,
        actor_role=admin.role,
    )
    await session.commit()
    return report
