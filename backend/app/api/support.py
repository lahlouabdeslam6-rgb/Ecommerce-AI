from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.order import OrderRepository
from app.repositories.support import SupportRepository
from app.schemas.order import OrderListResponse, OrderResponse, OrderStatusUpdate
from app.schemas.support import (
    SupportDashboardResponse,
    TicketListResponse,
    TicketPriorityUpdate,
    TicketReply,
    TicketResponse,
    TicketStatusUpdate,
)
from app.services.order import OrderService
from app.services.support import SupportService


router = APIRouter(prefix="/support", tags=["Support Workspace"])


@router.get("/dashboard", response_model=SupportDashboardResponse)
async def support_dashboard(
    _: Annotated[User, Depends(require_roles("support", "admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> SupportDashboardResponse:
    orders = await OrderRepository(session).dashboard_counts()
    tickets = await SupportRepository(session).dashboard_counts()
    return SupportDashboardResponse(
        orders=int(orders["orders"]),
        pending_orders=int(orders["pending_orders"]),
        delivered_orders=int(orders["delivered_orders"]),
        **tickets,
    )


@router.get("/orders", response_model=OrderListResponse)
async def support_orders(
    _: Annotated[User, Depends(require_roles("support", "admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    order_status: str | None = None,
) -> OrderListResponse:
    return await OrderService(session).list_orders(
        user_id=None,
        page=page,
        page_size=page_size,
        order_status=order_status,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def support_order(
    order_id: int,
    _: Annotated[User, Depends(require_roles("support", "admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OrderResponse:
    return await OrderService(session).get_order(order_id, None)


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
async def support_update_order(
    order_id: int,
    data: OrderStatusUpdate,
    support_user: Annotated[User, Depends(require_roles("support", "admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OrderResponse:
    return await OrderService(session).update_admin_status(
        order_id, data.order_status, support_user.id, support_user.role
    )


@router.get("/tickets", response_model=TicketListResponse)
async def support_tickets(
    _: Annotated[User, Depends(require_roles("support", "admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    ticket_status: str | None = None,
) -> TicketListResponse:
    return await SupportService(session).list_tickets(
        page=page,
        page_size=page_size,
        user_id=None,
        ticket_status=ticket_status,
    )


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def support_ticket(
    ticket_id: int,
    _: Annotated[User, Depends(require_roles("support", "admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TicketResponse:
    return await SupportService(session).get_ticket(ticket_id)


@router.post("/tickets/{ticket_id}/messages", response_model=TicketResponse)
async def support_reply(
    ticket_id: int,
    data: TicketReply,
    user: Annotated[User, Depends(require_roles("support", "admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TicketResponse:
    return await SupportService(session).reply(
        ticket_id, user, data.message, own_only=False
    )


@router.patch("/tickets/{ticket_id}/status", response_model=TicketResponse)
async def support_ticket_status(
    ticket_id: int,
    data: TicketStatusUpdate,
    support_user: Annotated[User, Depends(require_roles("support", "admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TicketResponse:
    return await SupportService(session).set_status(ticket_id, data.status, support_user)


@router.patch("/tickets/{ticket_id}/priority", response_model=TicketResponse)
async def support_ticket_priority(
    ticket_id: int,
    data: TicketPriorityUpdate,
    support_user: Annotated[User, Depends(require_roles("support", "admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TicketResponse:
    return await SupportService(session).set_priority(
        ticket_id, data.priority, support_user
    )
