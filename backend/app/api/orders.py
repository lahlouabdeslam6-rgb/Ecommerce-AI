from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.order import CheckoutRequest, OrderListResponse, OrderResponse
from app.services.order import OrderService


router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/checkout", response_model=OrderResponse, status_code=201)
async def checkout(
    data: CheckoutRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OrderResponse:
    return await OrderService(session).checkout(user.id, data)


@router.get("", response_model=OrderListResponse)
async def list_my_orders(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderListResponse:
    return await OrderService(session).list_orders(
        user_id=user.id,
        page=page,
        page_size=page_size,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_my_order(
    order_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OrderResponse:
    return await OrderService(session).get_order(order_id, user.id)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_my_order(
    order_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OrderResponse:
    return await OrderService(session).cancel_client_order(order_id, user.id)
