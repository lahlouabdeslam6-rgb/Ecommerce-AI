from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.order import OrderRepository
from app.repositories.operations import OperationsRepository
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.schemas.auth import (
    SupportUserCreate,
    SupportUserUpdate,
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.schemas.order import (
    DashboardResponse,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdate,
)
from app.services.auth import AuthService
from app.services.order import OrderService


router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/support-users", response_model=UserListResponse)
async def list_support_users(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
) -> UserListResponse:
    return await AuthService(session).list_users(
        page,
        page_size,
        role="support",
        search=search,
    )


@router.post(
    "/support-users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_support_user(
    data: SupportUserCreate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> User:
    support_user = await AuthService(session).create_support(data)
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="support_account.created",
        entity_type="user",
        entity_id=support_user.id,
        details={
            "email": support_user.email,
            "full_name": support_user.full_name,
            "is_active": support_user.is_active,
        },
    )
    await session.commit()
    return support_user


@router.patch("/support-users/{user_id}", response_model=UserResponse)
async def update_support_user(
    user_id: int,
    data: SupportUserUpdate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> User:
    before = await UserRepository(session).get_by_id(user_id)
    if before is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Support account not found")
    previous = {
        "email": before.email,
        "full_name": before.full_name,
    }
    support_user = await AuthService(session).update_support(user_id, data)
    changes = {
        field: {"before": previous[field], "after": getattr(support_user, field)}
        for field in ("email", "full_name")
        if previous[field] != getattr(support_user, field)
    }
    if data.password:
        changes["password"] = {"before": "hidden", "after": "updated"}
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="support_account.updated",
        entity_type="user",
        entity_id=user_id,
        details={"changes": changes},
    )
    await session.commit()
    return support_user


@router.delete(
    "/support-users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_support_user(
    user_id: int,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> None:
    target = await UserRepository(session).get_by_id(user_id)
    if target is None or target.role != "support" or target.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Support account not found")
    deleted_email = target.email
    await AuthService(session).delete_support(user_id)
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="support_account.deleted",
        entity_type="user",
        entity_id=user_id,
        details={"email": deleted_email, "deletion": "soft"},
    )
    await session.commit()


@router.get("/users", response_model=UserListResponse)
async def list_users(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
) -> UserListResponse:
    return await AuthService(session).list_users(
        page,
        page_size,
        search=search,
    )


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> User:
    if user_id == admin.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Admin cannot change their own role",
        )
    target = await UserRepository(session).get_by_id(user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    previous_role = target.role
    updated = await AuthService(session).set_role(user_id, data.role)
    if previous_role == updated.role:
        return updated
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="user.role_updated",
        entity_type="user",
        entity_id=user_id,
        details={
            "email": updated.email,
            "before": previous_role,
            "after": updated.role,
        },
    )
    await session.commit()
    return updated


@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> User:
    if user_id == admin.id and not data.is_active:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Admin cannot deactivate their own account",
        )
    target = await UserRepository(session).get_by_id(user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    previous_status = target.is_active
    updated = await AuthService(session).set_status(user_id, data.is_active)
    if previous_status == updated.is_active:
        return updated
    OperationsRepository(session).add_audit(
        actor_id=admin.id,
        actor_role=admin.role,
        action="user.activated" if data.is_active else "user.deactivated",
        entity_type="user",
        entity_id=user_id,
        details={
            "email": updated.email,
            "before": previous_status,
            "after": updated.is_active,
        },
    )
    await session.commit()
    return updated


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    order_status: str | None = None,
) -> OrderListResponse:
    return await OrderService(session).list_orders(
        user_id=None,
        page=page,
        page_size=page_size,
        order_status=order_status,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OrderResponse:
    return await OrderService(session).get_order(order_id, None)


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> OrderResponse:
    return await OrderService(session).update_admin_status(
        order_id, data.order_status, admin.id, admin.role
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    _: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> DashboardResponse:
    user_count = await UserRepository(session).count_users()
    catalog = await ProductRepository().catalog_counts()
    orders = await OrderRepository(session).dashboard_counts()
    return DashboardResponse(users=user_count, **catalog, **orders)
