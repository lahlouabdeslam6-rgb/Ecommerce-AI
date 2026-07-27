from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.support_agent import SupportAgentRequest, SupportAgentResponse
from app.services.support_agent import SupportAgentService


router = APIRouter(prefix="/support/ai", tags=["AI Support"])


@router.post("/chat", response_model=SupportAgentResponse)
async def support_agent_chat(
    data: SupportAgentRequest,
    user: Annotated[User, Depends(require_roles("customer"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> SupportAgentResponse:
    return await SupportAgentService(session, user).preview(data, use_ai=True)
