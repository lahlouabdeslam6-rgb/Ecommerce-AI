from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.admin import list_support_users, list_users
from app.api.products import manage_products
from app.models.user import User
from app.schemas.auth import UserListResponse
from app.schemas.product import ProductListResponse


def make_user(role: str) -> User:
    return User(
        id=1,
        email=f"{role}@example.com",
        hashed_password="test",
        role=role,
        token_version=1,
        is_active=True,
    )


@pytest.mark.asyncio
@patch("app.api.admin.AuthService")
async def test_admin_user_search_is_forwarded_to_repository(
    auth_service: MagicMock,
) -> None:
    expected = UserListResponse(
        items=[],
        total=0,
        page=1,
        page_size=100,
        total_pages=0,
    )
    auth_service.return_value.list_users = AsyncMock(return_value=expected)

    result = await list_users(
        make_user("admin"),
        AsyncMock(),
        page=1,
        page_size=100,
        search="ismail",
    )

    assert result == expected
    auth_service.return_value.list_users.assert_awaited_once_with(
        1,
        100,
        search="ismail",
    )


@pytest.mark.asyncio
@patch("app.api.admin.AuthService")
async def test_support_account_search_keeps_support_role_filter(
    auth_service: MagicMock,
) -> None:
    expected = UserListResponse(
        items=[],
        total=0,
        page=1,
        page_size=50,
        total_pages=0,
    )
    auth_service.return_value.list_users = AsyncMock(return_value=expected)

    result = await list_support_users(
        make_user("admin"),
        AsyncMock(),
        page=1,
        page_size=50,
        search="support@nutrifit.ma",
    )

    assert result == expected
    auth_service.return_value.list_users.assert_awaited_once_with(
        1,
        50,
        role="support",
        search="support@nutrifit.ma",
    )


@pytest.mark.asyncio
@patch("app.api.products.product_service")
async def test_staff_product_search_includes_hidden_products(
    product_service: MagicMock,
) -> None:
    expected = ProductListResponse(
        items=[],
        total=0,
        page=1,
        page_size=50,
        total_pages=0,
    )
    product_service.list_products = AsyncMock(return_value=expected)

    result = await manage_products(
        make_user("support"),
        page=1,
        page_size=50,
        search="whey",
    )

    assert result == expected
    product_service.list_products.assert_awaited_once_with(
        page=1,
        page_size=50,
        search="whey",
        brand=None,
        ingredient=None,
        category=None,
        flavor=None,
        min_price=None,
        max_price=None,
        in_stock=None,
        sort_by="newest",
        active_only=False,
    )
