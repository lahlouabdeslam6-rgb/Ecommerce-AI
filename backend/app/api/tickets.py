from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.support import (
    TicketCreate,
    TicketListResponse,
    TicketReply,
    TicketResponse,
)
from app.services.support import SupportService


router = APIRouter(prefix="/tickets", tags=["Customer Support"])


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    data: TicketCreate,
    user: Annotated[User, Depends(require_roles("customer"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TicketResponse:
    return await SupportService(session).create_ticket(user, data)


@router.get("", response_model=TicketListResponse)
async def list_my_tickets(
    user: Annotated[User, Depends(require_roles("customer"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TicketListResponse:
    return await SupportService(session).list_tickets(
        page=page, page_size=page_size, user_id=user.id
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_my_ticket(
    ticket_id: int,
    user: Annotated[User, Depends(require_roles("customer"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TicketResponse:
    return await SupportService(session).get_ticket(ticket_id, user_id=user.id)


@router.post("/{ticket_id}/messages", response_model=TicketResponse)
async def reply_to_my_ticket(
    ticket_id: int,
    data: TicketReply,
    user: Annotated[User, Depends(require_roles("customer"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TicketResponse:
    return await SupportService(session).reply(
        ticket_id, user, data.message, own_only=True
    )
