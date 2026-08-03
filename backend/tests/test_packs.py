from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.main import app
from app.schemas.order import GuestCartItemInput
from app.schemas.pack import PackCreate, PackListResponse
from app.services.pack import PackService


def test_pack_create_requires_two_distinct_products() -> None:
    with pytest.raises(ValidationError):
        PackCreate(
            name="Pack test",
            items=[{"product_id": 1, "quantity": 1}],
        )
    with pytest.raises(ValidationError):
        PackCreate(
            name="Pack test",
            items=[
                {"product_id": 1, "quantity": 1},
                {"product_id": 1, "quantity": 2},
            ],
        )


def test_guest_cart_item_accepts_exactly_one_kind() -> None:
    assert GuestCartItemInput(pack_id=4, quantity=1).pack_id == 4
    assert GuestCartItemInput(product_id=8, quantity=2).product_id == 8
    with pytest.raises(ValidationError):
        GuestCartItemInput(quantity=1)
    with pytest.raises(ValidationError):
        GuestCartItemInput(product_id=8, pack_id=4, quantity=1)


def test_pack_promotional_price_is_calculated_and_guarded() -> None:
    assert PackService._price(1000, 15, None) == 850
    assert PackService._price(1000, 15, 799) == 799
    with pytest.raises(HTTPException):
        PackService._price(1000, 10, 1100)


def test_pack_price_cannot_be_below_known_purchase_cost() -> None:
    PackService._validate_margin(850, 700)
    with pytest.raises(HTTPException) as exc:
        PackService._validate_margin(650, 700)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_pack_creation_keeps_cover_empty_and_builds_pack_summary() -> None:
    service = PackService(MagicMock())
    products = {
        10: {"name": "Whey Premium", "price": 300, "images": ["/product-whey.jpg"]},
        20: {"name": "Creatine Pure", "price": 200, "images": ["/product-creatine.jpg"]},
    }
    service._validate_items = AsyncMock(return_value=(products, 500, None))
    service._unique_slug = AsyncMock(return_value="pack-performance")
    service.repository = MagicMock()
    service.repository.create = AsyncMock(return_value=MagicMock())
    expected_response = MagicMock()
    service._response = AsyncMock(return_value=expected_response)

    result = await service.create(
        PackCreate(
            name="Pack performance",
            items=[{"product_id": 10}, {"product_id": 20}],
            discount_percentage=10,
        ),
        created_by=1,
    )

    values = service.repository.create.await_args.args[0]
    assert values["main_image_url"] is None
    assert "Whey Premium" in values["description"]
    assert "Creatine Pure" in values["description"]
    assert result is expected_response


@pytest.mark.asyncio
@patch("app.api.packs.PackService")
async def test_public_pack_list_endpoint(service_class: MagicMock) -> None:
    service_class.return_value.list_public = AsyncMock(
        return_value=PackListResponse(items=[], total=0)
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/packs")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


@pytest.mark.asyncio
async def test_sync_skips_non_pack_campaign() -> None:
    session = MagicMock()
    service = PackService(session)
    campaign = MagicMock(
        campaign_type="promotion",
        promotion_kind="single_product",
        created_at=datetime.now(UTC),
    )
    assert await service.sync_marketing_campaign(campaign, created_by=1) is None


@pytest.mark.asyncio
async def test_marketing_pack_receives_campaign_cover() -> None:
    service = PackService(MagicMock())
    service.repository = MagicMock()
    service.repository.get_by_campaign = AsyncMock(return_value=None)
    created = MagicMock(id=27)
    covered = MagicMock(id=27, main_image_url="/static/uploads/packs/campaign-cover.jpg")
    service.create = AsyncMock(return_value=created)
    service.set_main_image = AsyncMock(return_value=covered)
    campaign = MagicMock(
        id=8,
        campaign_type="promotion",
        promotion_kind="pack",
        product_ids=[10, 20],
        product_id=10,
        campaign_title="Pack performance",
        core_message="Une selection complete pour la routine sportive.",
        headline="Deux produits complementaires",
        discount_percentage=8,
        starts_at=None,
        ends_at=None,
        pack_cover_image_url="/static/uploads/packs/campaign-cover.jpg",
    )

    result = await service.sync_marketing_campaign(campaign, created_by=1)

    service.set_main_image.assert_awaited_once_with(
        27,
        "/static/uploads/packs/campaign-cover.jpg",
    )
    assert result is covered
