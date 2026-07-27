from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.schemas.orchestrator import OrchestratorRequest
from app.schemas.stock_forecast import StockForecastReport
from app.services.orchestrator_service import OrchestratorService
from app.services.stock_forecast_agent import StockForecastAgentService


class FakeSalesRepository:
    async def product_sales(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[int, int]:
        if (datetime.now(UTC) - end).total_seconds() < 60:
            return {1: 30, 2: 30, 3: 30, 4: 30}
        return {1: 15, 2: 15, 3: 30, 4: 60}


class FakeProductRepository:
    async def list_products(self, **_: object) -> tuple[list[dict], int]:
        products = [
            {
                "product_id": 1,
                "name": "Produit en rupture",
                "brand": "NUTRIFIT",
                "stock": 0,
                "price": 100,
            },
            {
                "product_id": 2,
                "name": "Produit critique",
                "brand": "NUTRIFIT",
                "stock": 5,
                "price": 120,
            },
            {
                "product_id": 3,
                "name": "Produit à surveiller",
                "brand": "NUTRIFIT",
                "stock": 15,
                "price": 150,
            },
            {
                "product_id": 4,
                "name": "Produit stable",
                "brand": "NUTRIFIT",
                "stock": 100,
                "price": 180,
            },
            {
                "product_id": 5,
                "name": "Produit sans vente",
                "brand": "NUTRIFIT",
                "stock": 20,
                "price": 90,
            },
        ]
        return products, len(products)


@pytest.mark.asyncio
async def test_forecast_classifies_risks_and_reorder_quantities() -> None:
    service = StockForecastAgentService(
        None,  # type: ignore[arg-type]
        repository=FakeSalesRepository(),  # type: ignore[arg-type]
        product_repository=FakeProductRepository(),  # type: ignore[arg-type]
    )
    report = await service.report(30, use_ai=False)

    by_id = {item.product_id: item for item in report.items}
    assert by_id[1].risk == "out_of_stock"
    assert by_id[2].risk == "critical"
    assert by_id[2].days_remaining == 5
    assert by_id[2].recommended_reorder_quantity == 25
    assert by_id[3].risk == "warning"
    assert by_id[4].risk == "healthy"
    assert by_id[5].risk == "dormant"
    assert report.summary.products == 5
    assert report.summary.recommended_reorder_units == 70
    assert report.model == "prévision locale"
    assert report.read_only is True


@pytest.mark.asyncio
async def test_ai_analysis_can_replace_local_text_without_mutation() -> None:
    service = StockForecastAgentService(
        None,  # type: ignore[arg-type]
        repository=FakeSalesRepository(),  # type: ignore[arg-type]
        product_repository=FakeProductRepository(),  # type: ignore[arg-type]
    )
    service._generate_ai_analysis = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            "Analyse IA fondée sur les chiffres.",
            ["Le produit critique doit être surveillé."],
            ["Risque de rupture détecté."],
        )
    )

    report = await service.report(30, use_ai=True)

    assert report.analysis.startswith("Analyse IA")
    assert report.insights == ["Le produit critique doit être surveillé."]
    assert report.read_only is True
    service._generate_ai_analysis.assert_awaited_once()


def sample_report() -> StockForecastReport:
    return StockForecastReport(
        lookback_days=30,
        target_cover_days=30,
        generated_at=datetime.now(UTC),
        summary={
            "products": 0,
            "out_of_stock": 0,
            "critical": 0,
            "warning": 0,
            "healthy": 0,
            "dormant": 0,
            "recommended_reorder_units": 0,
        },
        items=[],
        analysis="Aucune priorité.",
        insights=[],
        alerts=[],
        model="prévision locale",
        read_only=True,
    )


@pytest.mark.asyncio
@patch("app.api.stock_forecast.StockForecastAgentService")
@patch("app.core.security.UserRepository.get_by_id")
async def test_admin_can_access_stock_forecast(
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
            "/api/admin/ai/stock-forecast/report?lookback_days=30",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["read_only"] is True
    mock_service_class.return_value.report.assert_awaited_once_with(
        30,
        target_cover_days=30,
        use_ai=False,
    )


@pytest.mark.asyncio
@patch("app.api.stock_forecast.StockForecastAgentService")
@patch("app.core.security.UserRepository.get_by_id")
async def test_customer_cannot_access_stock_forecast(
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
            "/api/admin/ai/stock-forecast/report",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    mock_service_class.assert_not_called()


def test_orchestrator_detects_stock_forecast_request() -> None:
    service = OrchestratorService()
    assert (
        service._detect_domain_intent(
            "Prévois les risques de rupture de stock",
            None,
        )
        == "stock_forecast"
    )


@pytest.mark.asyncio
@patch("app.services.orchestrator_service.StockForecastAgentService")
async def test_orchestrator_routes_admin_to_stock_forecast(
    mock_forecast_class: MagicMock,
) -> None:
    user = User(id=1, role="admin", token_version=1, is_active=True)
    mock_forecast_class.return_value.report = AsyncMock(
        return_value=sample_report()
    )
    service = OrchestratorService(session=AsyncMock(), user=user)
    service._run_safety = AsyncMock(return_value=None)  # type: ignore[method-assign]

    response = await service.execute(
        OrchestratorRequest(
            message="Prévois les risques de rupture de stock",
            task_type="stock_forecast",
            context={"lookback_days": 30},
        )
    )

    assert response.detected_intent == "stock_forecast"
    assert response.selected_agents == ["stock_forecast"]
    assert response.results[0].data["read_only"] is True
    mock_forecast_class.return_value.report.assert_awaited_once_with(
        30,
        target_cover_days=30,
        use_ai=False,
    )


@pytest.mark.asyncio
async def test_orchestrator_rejects_customer_stock_forecast() -> None:
    user = User(id=2, role="customer", token_version=1, is_active=True)
    service = OrchestratorService(session=AsyncMock(), user=user)

    with pytest.raises(HTTPException) as error:
        await service.execute(
            OrchestratorRequest(
                message="Prévision de rupture",
                task_type="stock_forecast",
            )
        )

    assert error.value.status_code == 403
