from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.seo import SEOApplyResponse, SEOAuditReport, SEOProposal
from app.services.seo_agent import SEOAgentService


router = APIRouter(prefix="/admin/ai/seo", tags=["AI SEO"])


@router.get("/audit", response_model=SEOAuditReport)
async def seo_audit(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> SEOAuditReport:
    return await SEOAgentService(session).audit()


@router.post("/products/{product_id}/preview", response_model=SEOProposal)
async def seo_preview(
    product_id: int,
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> SEOProposal:
    return await SEOAgentService(session).preview(product_id)


@router.post(
    "/products/{product_id}/apply",
    response_model=SEOApplyResponse,
)
async def seo_apply(
    product_id: int,
    proposal: SEOProposal,
    user: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> SEOApplyResponse:
    return await SEOAgentService(session).apply(product_id, proposal, user)

