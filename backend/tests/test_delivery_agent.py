from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.schemas.delivery import DeliveryReport
from app.schemas.orchestrator import OrchestratorRequest
from app.services.delivery_agent import DeliveryAgentService
from app.services.orchestrator_service import OrchestratorService


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
    status: str,
    age_hours: int,
) -> MagicMock:
    order = MagicMock()
    order.id = order_id
    order.user_id = 10 + order_id
    order.full_name = f"Client {order_id}"
    order.phone = f"+2126000000{order_id}"
    order.city = "Casablanca"
    order.order_status = status
    order.created_at = datetime.now(UTC) - timedelta(hours=age_hours)
    order.total = 300.0 + order_id
    order.currency = "MAD"
    return order


def test_delivery_agent_accepts_guest_order() -> None:
    order = make_order(9, "pending", 2)
    order.user_id = None
    item = DeliveryAgentService._assess_order(
        order,
        "invite@example.com",
        datetime.now(UTC),
    )
    assert item.user_id is None
    assert item.customer_email == "invite@example.com"


class FakeDeliveryRepository:
    def __init__(self) -> None:
        self.rows = [
            (make_order(1, "pending", 4), "one@example.com"),
            (make_order(2, "confirmed", 40), "two@example.com"),
            (make_order(3, "preparing", 80), "three@example.com"),
            (make_order(4, "delivery_failed", 5), "four@example.com"),
        ]
        self.alert_sent_since = AsyncMock(return_value=False)

    async def active_orders(self) -> list[tuple[MagicMock, str]]:
        return self.rows


@pytest.mark.asyncio
async def test_delivery_report_classifies_operational_risk() -> None:
    service = DeliveryAgentService(
        AsyncMock(),
        repository=FakeDeliveryRepository(),  # type: ignore[arg-type]
        operations=MagicMock(),
        automation=MagicMock(),
    )

    report = await service.report(notify=False)

    by_id = {item.order_id: item for item in report.items}
    assert by_id[1].risk == "normal"
    assert by_id[2].risk == "warning"
    assert by_id[3].risk == "critical"
    assert by_id[4].risk == "failed"
    assert report.summary.active_orders == 4
    assert report.read_only is True


@pytest.mark.asyncio
async def test_delivery_scan_notifies_each_priority_order_once() -> None:
    repository = FakeDeliveryRepository()
    operations = MagicMock()
    automation = MagicMock()
    session = AsyncMock()
    service = DeliveryAgentService(
        session,
        repository=repository,  # type: ignore[arg-type]
        operations=operations,
        automation=automation,
    )

    report = await service.report(notify=True, actor=make_user())

    assert report.summary.alerts_sent == 2
    assert operations.add_notification.call_count == 6
    assert operations.add_audit.call_count == 2
    assert automation.add_outbox.call_count == 4
    session.commit.assert_awaited_once()


def sample_report() -> DeliveryReport:
    return DeliveryReport(
        generated_at=datetime.now(UTC),
        summary={
            "active_orders": 0,
            "normal": 0,
            "warning": 0,
            "critical": 0,
            "failed": 0,
            "alerts_sent": 0,
        },
        items=[],
        analysis="Aucune commande active à surveiller.",
    )


@pytest.mark.asyncio
@patch("app.api.delivery.DeliveryAgentService")
@patch("app.core.security.UserRepository.get_by_id")
async def test_admin_can_run_delivery_scan(
    get_user: MagicMock,
    delivery_class: MagicMock,
) -> None:
    get_user.return_value = make_user()
    delivery_class.return_value.report = AsyncMock(return_value=sample_report())
    token = create_access_token(user_id=1, role="admin", token_version=1)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/admin/ai/delivery/scan",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    delivery_class.return_value.report.assert_awaited_once()


@pytest.mark.asyncio
async def test_customer_cannot_use_delivery_agent() -> None:
    service = OrchestratorService(session=AsyncMock(), user=make_user("customer"))
    with pytest.raises(HTTPException) as error:
        await service.execute(
            OrchestratorRequest(
                message="Analyse les retards de livraison",
                task_type="delivery",
            )
        )
    assert error.value.status_code == 403


def test_orchestrator_detects_delivery_analysis() -> None:
    assert (
        OrchestratorService()._detect_domain_intent(
            "Analyse les risques et retards de livraison",
            None,
        )
        == "delivery"
    )


@pytest.mark.asyncio
@patch("app.services.orchestrator_service.DeliveryAgentService")
async def test_orchestrator_routes_admin_to_delivery(
    delivery_class: MagicMock,
) -> None:
    delivery_class.return_value.report = AsyncMock(return_value=sample_report())
    service = OrchestratorService(session=AsyncMock(), user=make_user())

    response = await service.execute(
        OrchestratorRequest(
            message="Analyse les retards de livraison",
            task_type="delivery",
        )
    )

    assert response.detected_intent == "delivery"
    assert response.selected_agents == ["delivery"]
    assert response.results[0].data["read_only"] is True
