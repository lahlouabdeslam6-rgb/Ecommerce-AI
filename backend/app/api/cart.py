from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartResponse, PackCartItemAdd
from app.services.cart import CartService


router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get("", response_model=CartResponse)
async def get_cart(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> CartResponse:
    return await CartService(session).get_cart(user.id)


@router.post("/items", response_model=CartResponse)
async def add_cart_item(
    data: CartItemAdd,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> CartResponse:
    return await CartService(session).add_item(
        user.id, data.product_id, data.quantity
    )


@router.patch("/items/{product_id}", response_model=CartResponse)
async def update_cart_item(
    product_id: int,
    data: CartItemUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> CartResponse:
    return await CartService(session).update_item(
        user.id, product_id, data.quantity
    )


@router.delete("/items/{product_id}", response_model=CartResponse)
async def remove_cart_item(
    product_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> CartResponse:
    return await CartService(session).remove_item(user.id, product_id)


@router.post("/packs", response_model=CartResponse)
async def add_pack_item(
    data: PackCartItemAdd,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> CartResponse:
    return await CartService(session).add_pack(user.id, data.pack_id, data.quantity)


@router.patch("/packs/{pack_id}", response_model=CartResponse)
async def update_pack_item(
    pack_id: int,
    data: CartItemUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> CartResponse:
    return await CartService(session).update_pack(user.id, pack_id, data.quantity)


@router.delete("/packs/{pack_id}", response_model=CartResponse)
async def remove_pack_item(
    pack_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> CartResponse:
    return await CartService(session).remove_pack(user.id, pack_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> Response:
    await CartService(session).clear(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
