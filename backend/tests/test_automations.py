from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.automation import AutomationOutbox
from app.services.automation import AutomationService


class FakeAutomationRepository:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.add_outbox = MagicMock()

    async def abandoned_carts(
        self,
        *,
        older_than: datetime,
    ) -> list[tuple[int, str, datetime, int]]:
        return [(7, "client@example.com", datetime.now(UTC), 3)]

    async def event_logged_recently(self, **_: object) -> bool:
        return self.duplicate


@pytest.mark.asyncio
async def test_abandoned_cart_scan_queues_email_and_notification() -> None:
    repository = FakeAutomationRepository()
    operations = MagicMock()
    session = AsyncMock()
    service = AutomationService(
        session,
        repository=repository,  # type: ignore[arg-type]
        operations=operations,
    )

    result = await service.scan_abandoned_carts(older_than_hours=24)

    assert result.scanned == 1
    assert result.notifications_created == 1
    assert result.outbox_created == 1
    operations.add_notification.assert_called_once()
    operations.add_audit.assert_called_once()
    repository.add_outbox.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_abandoned_cart_scan_deduplicates_for_seven_days() -> None:
    repository = FakeAutomationRepository(duplicate=True)
    operations = MagicMock()
    session = AsyncMock()
    result = await AutomationService(
        session,
        repository=repository,  # type: ignore[arg-type]
        operations=operations,
    ).scan_abandoned_carts()
    assert result.notifications_created == 0
    repository.add_outbox.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_automation_endpoint_rejects_invalid_key() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/automations/carts/abandoned",
            headers={"X-Automation-Key": "wrong"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.api.automations.AutomationService")
async def test_automation_endpoint_accepts_internal_key(
    service_class: MagicMock,
) -> None:
    service_class.return_value.scan_abandoned_carts = AsyncMock(
        return_value={
            "scanned": 2,
            "notifications_created": 1,
            "outbox_created": 1,
        }
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/automations/carts/abandoned",
            headers={"X-Automation-Key": settings.automation_api_key},
        )
    assert response.status_code == 200
    assert response.json()["outbox_created"] == 1


@pytest.mark.asyncio
async def test_outbox_completion_marks_success() -> None:
    item = AutomationOutbox(
        id=5,
        event_type="delivery_alert",
        channel="email",
        recipient="client@example.com",
        body="Message",
        status="sent",
        attempts=1,
        created_at=datetime.now(UTC),
    )
    repository = MagicMock()
    repository.complete_outbox = AsyncMock(return_value=item)
    result = await AutomationService(
        AsyncMock(),
        repository=repository,
    ).complete_outbox(5, success=True, error=None)
    assert result.id == 5
    assert result.status == "sent"

