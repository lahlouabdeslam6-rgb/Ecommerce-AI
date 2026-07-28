from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.schemas.orchestrator import OrchestratorRequest
from app.schemas.order_verification import OrderVerificationReport
from app.services.orchestrator_service import OrchestratorService
from app.services.order_verification_agent import OrderVerificationAgentService


def make_user(role: str = "admin") -> User:
    return User(
        id=1,
        email=f"{role}@example.com",
        hashed_password="test",
        role=role,
        token_version=1,
        is_active=True,
    )


def make_order(
    order_id: int,
    *,
    status: str = "pending",
    phone: str = "+212600000001",
    email: str = "client@example.com",
    address: str = "10 rue Atlas",
    user_id: int | None = None,
    total: float = 300,
    age_hours: int = 1,
) -> MagicMock:
    order = MagicMock()
    order.id = order_id
    order.user_id = user_id
    order.email = email
    order.full_name = "Client Test"
    order.phone = phone
    order.address = address
    order.city = "Casablanca"
    order.total = total
    order.currency = "MAD"
    order.payment_method = "cash_on_delivery"
    order.order_status = status
    order.created_at = datetime.now(UTC) - timedelta(hours=age_hours)
    return order


class FakeVerificationRepository:
    def __init__(self, orders: list[MagicMock]) -> None:
        self.orders = orders

    async def recent_orders(self, _: datetime) -> list[MagicMock]:
        return self.orders


@pytest.mark.asyncio
async def test_agent_detects_possible_duplicate_without_mutating() -> None:
    current = make_order(2)
    previous = make_order(1, status="confirmed", age_hours=2)
    service = OrderVerificationAgentService(
        AsyncMock(),
        repository=FakeVerificationRepository([current, previous]),  # type: ignore[arg-type]
    )

    report = await service.report()

    assert report.summary.possible_duplicate == 1
    assert report.items[0].verification_status == "possible_duplicate"
    assert report.read_only is True
    assert report.automatic_rejection is False


@pytest.mark.asyncio
async def test_delivered_customer_can_be_marked_ready_for_human_confirmation() -> None:
    current = make_order(2, user_id=8)
    delivered = make_order(1, status="delivered", user_id=8, age_hours=72)
    service = OrderVerificationAgentService(
        AsyncMock(),
        repository=FakeVerificationRepository([current, delivered]),  # type: ignore[arg-type]
    )

    report = await service.report()

    assert report.items[0].verification_status == "ready_to_prepare"
    assert "Confirmer humainement" in report.items[0].recommended_action


def sample_report() -> OrderVerificationReport:
    return OrderVerificationReport(
        generated_at=datetime.now(UTC),
        summary={
            "orders_to_review": 0,
            "to_confirm": 0,
            "priority_review": 0,
            "possible_duplicate": 0,
            "ready_to_prepare": 0,
        },
        items=[],
        analysis="Aucune commande en attente de vérification.",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["admin", "support"])
@patch("app.api.order_verification.OrderVerificationAgentService")
@patch("app.core.security.UserRepository.get_by_id")
async def test_staff_can_open_verification_report(
    get_user: MagicMock,
    service_class: MagicMock,
    role: str,
) -> None:
    get_user.return_value = make_user(role)
    service_class.return_value.report = AsyncMock(return_value=sample_report())
    token = create_access_token(user_id=1, role=role, token_version=1)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/ai/order-verification/report",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["automatic_rejection"] is False


def test_orchestrator_detects_order_verification_intent() -> None:
    assert (
        OrchestratorService()._detect_domain_intent(
            "Vérifier les commandes COD et les doublons",
            None,
        )
        == "order_verification"
    )


@pytest.mark.asyncio
@patch("app.services.orchestrator_service.OrderVerificationAgentService")
async def test_orchestrator_routes_support_to_order_verification(
    service_class: MagicMock,
) -> None:
    service_class.return_value.report = AsyncMock(return_value=sample_report())
    orchestrator = OrchestratorService(
        session=AsyncMock(),
        user=make_user("support"),
    )

    result = await orchestrator.execute(
        OrchestratorRequest(
            message="Vérifier les commandes COD et les doublons",
            task_type="order_verification",
        )
    )

    assert result.detected_intent == "order_verification"
    assert result.selected_agents == ["order_verification"]


@pytest.mark.asyncio
async def test_customer_cannot_use_order_verification_agent() -> None:
    orchestrator = OrchestratorService(
        session=AsyncMock(),
        user=make_user("customer"),
    )
    with pytest.raises(HTTPException) as error:
        await orchestrator.execute(
            OrchestratorRequest(
                message="Vérifier les commandes",
                task_type="order_verification",
            )
        )
    assert error.value.status_code == 403
