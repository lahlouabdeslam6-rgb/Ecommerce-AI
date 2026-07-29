from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.order import Order
from app.repositories.order import OrderRepository
from app.schemas.order import GuestCheckoutResponse, OrderResponse
from app.services.order import OrderService


def sample_order() -> OrderResponse:
    now = datetime.now(UTC)
    return OrderResponse(
        id=91,
        user_id=None,
        email="invite@example.com",
        order_status="pending",
        payment_method="cash_on_delivery",
        payment_status="pending",
        card_last4=None,
        card_brand=None,
        payment_reference=None,
        full_name="Client Invite",
        phone="0612345678",
        address="Adresse livraison 12",
        city="Casablanca",
        notes=None,
        subtotal=299,
        delivery_fee=0,
        total=299,
        currency="MAD",
        created_at=now,
        updated_at=now,
        items=[
            {
                "product_id": 15207,
                "product_name": "Creatine",
                "brand": "NUTRIFIT",
                "image_url": None,
                "unit_price": 299,
                "quantity": 1,
                "subtotal": 299,
            }
        ],
    )


@pytest.mark.asyncio
@patch("app.api.orders.OrderService")
async def test_guest_checkout_requires_no_authentication(
    service_class: MagicMock,
) -> None:
    service_class.return_value.guest_checkout = AsyncMock(
        return_value=GuestCheckoutResponse(
            order=sample_order(),
            tracking_token="a" * 43,
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/orders/guest-checkout",
            json={
                "full_name": "Client Invite",
                "phone": "0612345678",
                "city": "Casablanca",
                "payment_method": "cash_on_delivery",
                "items": [{"product_id": 15207, "quantity": 1}],
            },
        )

    assert response.status_code == 201
    assert response.json()["order"]["user_id"] is None
    assert response.json()["tracking_token"]
    checkout_data = service_class.return_value.guest_checkout.await_args.args[0]
    assert checkout_data.email is None
    assert checkout_data.address is None


@pytest.mark.asyncio
async def test_guest_checkout_rejects_empty_cart() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/orders/guest-checkout",
            json={
                "email": "invite@example.com",
                "full_name": "Client Invite",
                "phone": "0612345678",
                "address": "Adresse livraison 12",
                "city": "Casablanca",
                "items": [],
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_guest_tracking_rejects_wrong_secret() -> None:
    session = AsyncMock()
    service = OrderService(session)
    order = Order(
        id=91,
        user_id=None,
        email="invite@example.com",
        guest_token_hash=service._token_hash("correct-token-value-1234567890"),
    )
    service.order_repository.get_by_id = AsyncMock(return_value=order)

    with pytest.raises(HTTPException) as error:
        await service.track_guest_order(
            91,
            "wrong-token-value-12345678901234567890",
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_order_uses_phone_confirmation_when_address_is_omitted() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    repository = OrderRepository(session)

    order = await repository.create(
        user_id=None,
        email="guest-test@orders.nutrifit.ma",
        shipping={
            "full_name": "Client Invite",
            "phone": "0612345678",
            "city": "Kenitra",
            "address": None,
            "notes": None,
        },
        items=[
            {
                "product_id": 15207,
                "product_name": "Creatine",
                "brand": "NUTRIFIT",
                "image_url": None,
                "unit_price": 200,
                "quantity": 1,
                "subtotal": 200,
            }
        ],
        subtotal=200,
        delivery_fee=0,
        payment_method="cash_on_delivery",
        payment_status="pending",
    )

    assert order.address == "A confirmer par telephone"
    session.add.assert_called_once_with(order)
    session.flush.assert_awaited_once()
