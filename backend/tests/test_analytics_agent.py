from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.sqlite import Base
from app.main import app
from app.models.order import Order, OrderItem
from app.models.user import User
from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import AnalyticsReport
from app.schemas.orchestrator import OrchestratorRequest
from app.services.analytics_agent import AnalyticsAgentService
from app.services.orchestrator_service import OrchestratorService


class FakeAnalyticsRepository:
    async def metrics(self, start: datetime, end: datetime) -> dict:
        if (datetime.now(UTC) - end).total_seconds() < 60:
            return {
                "orders": 10,
                "paid_orders": 8,
                "delivered_orders": 8,
                "cancelled_orders": 2,
                "units_sold": 16,
                "revenue_mad": 2400,
                "average_order_value_mad": 300,
            }
        return {
            "orders": 5,
            "paid_orders": 4,
            "delivered_orders": 4,
            "cancelled_orders": 1,
            "units_sold": 8,
            "revenue_mad": 1200,
            "average_order_value_mad": 300,
        }

    async def daily_sales(self, start: datetime, end: datetime) -> list[dict]:
        return [
            {
                "date": start.date().isoformat(),
                "orders": 2,
                "revenue_mad": 600,
            }
        ]

    async def top_products(
        self,
        start: datetime,
        end: datetime,
        *,
        limit: int = 8,
    ) -> list[dict]:
        return [
            {
                "product_id": 1,
                "name": "Créatine Premium",
                "brand": "NUTRIFIT",
                "quantity": 9,
                "revenue_mad": 1350,
            }
        ]

    async def sold_product_ids(
        self,
        start: datetime,
        end: datetime,
    ) -> set[int]:
        return {1}


class FakeProductRepository:
    async def list_products(self, **_: object) -> tuple[list[dict], int]:
        products = [
            {
                "product_id": 1,
                "name": "Créatine Premium",
                "brand": "NUTRIFIT",
                "stock": 12,
                "price": 150,
            },
            {
                "product_id": 2,
                "name": "Omega 3",
                "brand": "NUTRIFIT",
                "stock": 30,
                "price": 220,
            },
        ]
        return products, len(products)


@pytest.mark.asyncio
async def test_repository_aggregates_real_sqlite_orders() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    async with sessions() as session:
        session.add(
            Order(
                user_id=1,
                order_status="delivered",
                payment_method="card",
                payment_status="paid",
                full_name="Client Test",
                phone="0600000000",
                address="Adresse test",
                city="Casablanca",
                subtotal=500,
                delivery_fee=0,
                total=500,
                currency="MAD",
                created_at=now,
                updated_at=now,
                items=[
                    OrderItem(
                        product_id=10,
                        product_name="Whey Premium",
                        brand="NUTRIFIT",
                        unit_price=250,
                        quantity=2,
                        subtotal=500,
                    )
                ],
            )
        )
        await session.commit()

        repository = AnalyticsRepository(session)
        metrics = await repository.metrics(
            now.replace(hour=0, minute=0, second=0, microsecond=0),
            now + timedelta(days=1),
        )
        products = await repository.top_products(
            now.replace(hour=0, minute=0, second=0, microsecond=0),
            now + timedelta(days=1),
        )

    await engine.dispose()
    assert metrics["orders"] == 1
    assert metrics["revenue_mad"] == 500
    assert metrics["units_sold"] == 2
    assert products[0]["product_id"] == 10
    assert products[0]["quantity"] == 2


@pytest.mark.asyncio
async def test_report_calculates_trends_and_unsold_products() -> None:
    service = AnalyticsAgentService(
        None,  # type: ignore[arg-type]
        repository=FakeAnalyticsRepository(),  # type: ignore[arg-type]
        product_repository=FakeProductRepository(),  # type: ignore[arg-type]
    )
    result = await service.report(30, use_ai=False)

    assert result.current.revenue_mad == 2400
    assert result.comparison.revenue_change_pct == 100
    assert result.comparison.orders_change_pct == 100
    assert result.top_products[0].product_id == 1
    assert result.unsold_products[0].product_id == 2
    assert len(result.daily_sales) == 30
    assert result.model == "analyse locale"
    assert result.read_only is True


@pytest.mark.asyncio
async def test_ai_summary_replaces_local_summary_without_mutation() -> None:
    service = AnalyticsAgentService(
        None,  # type: ignore[arg-type]
        repository=FakeAnalyticsRepository(),  # type: ignore[arg-type]
        product_repository=FakeProductRepository(),  # type: ignore[arg-type]
    )
    service._generate_ai_analysis = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            "Résumé IA fondé sur les chiffres fournis.",
            ["La créatine domine les ventes."],
            [],
        )
    )

    result = await service.report(30, use_ai=True)

    assert result.summary.startswith("Résumé IA")
    assert result.insights == ["La créatine domine les ventes."]
    assert result.read_only is True
    service._generate_ai_analysis.assert_awaited_once()


def sample_report() -> AnalyticsReport:
    return AnalyticsReport(
        period_days=30,
        generated_at=datetime.now(UTC),
        current={
            "orders": 0,
            "paid_orders": 0,
            "delivered_orders": 0,
            "cancelled_orders": 0,
            "units_sold": 0,
            "revenue_mad": 0,
            "average_order_value_mad": 0,
        },
        previous={
            "orders": 0,
            "paid_orders": 0,
            "delivered_orders": 0,
            "cancelled_orders": 0,
            "units_sold": 0,
            "revenue_mad": 0,
            "average_order_value_mad": 0,
        },
        comparison={
            "orders_change_pct": 0,
            "revenue_change_pct": 0,
            "units_change_pct": 0,
        },
        daily_sales=[],
        top_products=[],
        unsold_products=[],
        summary="Aucune commande.",
        insights=[],
        alerts=[],
        model="analyse locale",
        read_only=True,
    )


@pytest.mark.asyncio
@patch("app.api.analytics.AnalyticsAgentService")
@patch("app.core.security.UserRepository.get_by_id")
async def test_admin_can_access_analytics_report(
    mock_get_by_id: MagicMock,
    mock_service_class: MagicMock,
) -> None:
    mock_get_by_id.return_value = User(
        id=1,
        role="admin",
        token_version=1,
        is_active=True,
    )
    mock_service_class.return_value.report = AsyncMock(
        return_value=sample_report()
    )
    token = create_access_token(user_id=1, role="admin", token_version=1)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/admin/ai/analytics/report?period_days=30",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["read_only"] is True
    mock_service_class.return_value.report.assert_awaited_once_with(
        30,
        use_ai=False,
    )


@pytest.mark.asyncio
@patch("app.api.analytics.AnalyticsAgentService")
@patch("app.core.security.UserRepository.get_by_id")
async def test_customer_cannot_access_analytics_report(
    mock_get_by_id: MagicMock,
    mock_service_class: MagicMock,
) -> None:
    mock_get_by_id.return_value = User(
        id=2,
        role="customer",
        token_version=1,
        is_active=True,
    )
    token = create_access_token(user_id=2, role="customer", token_version=1)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/admin/ai/analytics/report",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    mock_service_class.assert_not_called()


def test_orchestrator_detects_french_analytics_request() -> None:
    service = OrchestratorService()
    assert (
        service._detect_domain_intent(
            "Analyse les ventes et le revenu des 30 derniers jours",
            None,
        )
        == "analytics"
    )


@pytest.mark.asyncio
@patch("app.services.orchestrator_service.AnalyticsAgentService")
async def test_orchestrator_routes_admin_to_analytics_agent(
    mock_analytics_class: MagicMock,
) -> None:
    user = User(id=1, role="admin", token_version=1, is_active=True)
    mock_analytics_class.return_value.report = AsyncMock(
        return_value=sample_report()
    )
    service = OrchestratorService(session=AsyncMock(), user=user)
    service._run_safety = AsyncMock(return_value=None)  # type: ignore[method-assign]

    response = await service.execute(
        OrchestratorRequest(
            message="Analyse les ventes des 30 derniers jours",
            task_type="analytics",
            context={"period_days": 30},
        )
    )

    assert response.detected_intent == "analytics"
    assert response.selected_agents == ["analytics"]
    assert response.results[0].data["read_only"] is True
    mock_analytics_class.return_value.report.assert_awaited_once_with(
        30,
        use_ai=False,
    )


@pytest.mark.asyncio
async def test_orchestrator_rejects_customer_analytics_request() -> None:
    user = User(id=2, role="customer", token_version=1, is_active=True)
    service = OrchestratorService(session=AsyncMock(), user=user)

    with pytest.raises(HTTPException) as error:
        await service.execute(
            OrchestratorRequest(
                message="Analyse les ventes",
                task_type="analytics",
            )
        )

    assert getattr(error.value, "status_code", None) == 403
