from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.schemas.orchestrator import OrchestratorRequest
from app.services.orchestrator_service import OrchestratorService
from app.services.seo_agent import SEOAgentService


PRODUCT = {
    "product_id": 20,
    "name": "Creatine Monohydrate",
    "brand": "NUTRIFIT",
    "category": "Créatine",
    "description": "Description courte.",
    "images": ["/static/creatine.jpg"],
    "ingredients": [{"name": "Créatine monohydrate"}],
    "seo_title": None,
    "seo_description": None,
    "seo_keywords": [],
}


class FakeProductRepository:
    def __init__(self) -> None:
        self.product = dict(PRODUCT)

    async def list_products(self, **_: object) -> tuple[list[dict], int]:
        return [dict(self.product)], 1

    async def get_by_product_id(self, product_id: int) -> dict | None:
        return dict(self.product) if product_id == 20 else None

    async def update_product(
        self,
        product_id: int,
        fields: dict,
    ) -> dict | None:
        if product_id != 20:
            return None
        self.product.update(fields)
        return dict(self.product)


def admin() -> User:
    return User(
        id=1,
        email="admin@example.com",
        hashed_password="test",
        role="admin",
        token_version=1,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_seo_audit_scores_missing_fields() -> None:
    service = SEOAgentService(
        AsyncMock(),
        product_repository=FakeProductRepository(),  # type: ignore[arg-type]
    )
    report = await service.audit()
    assert report.summary.products == 1
    assert report.summary.critical == 1
    assert report.items[0].score < 50
    assert "Slug SEO absent" in report.items[0].issues


@pytest.mark.asyncio
async def test_seo_preview_generates_complete_safe_metadata() -> None:
    service = SEOAgentService(
        AsyncMock(),
        product_repository=FakeProductRepository(),  # type: ignore[arg-type]
    )
    proposal = await service.preview(20)
    assert proposal.slug == "creatine-monohydrate-20"
    assert len(proposal.seo_title) >= 10
    assert len(proposal.seo_description) >= 40
    assert len(proposal.seo_keywords) >= 3
    assert len(proposal.seo_faq) == 2
    assert proposal.read_only is True


@pytest.mark.asyncio
@patch("app.services.seo_agent.SafetyAgentService")
async def test_seo_apply_requires_safety_and_improves_score(
    safety_class: MagicMock,
) -> None:
    repository = FakeProductRepository()
    operations = MagicMock()
    session = AsyncMock()
    safety_class.return_value.enforce = AsyncMock()
    service = SEOAgentService(
        session,
        product_repository=repository,  # type: ignore[arg-type]
        operations=operations,
    )
    proposal = await service.preview(20)

    result = await service.apply(20, proposal, admin())

    assert result.score_after > result.score_before
    safety_class.return_value.enforce.assert_awaited_once()
    operations.add_audit.assert_called_once()
    session.commit.assert_awaited_once()


def test_orchestrator_detects_seo_audit() -> None:
    assert (
        OrchestratorService()._detect_domain_intent(
            "Lance un audit SEO du catalogue",
            None,
        )
        == "seo"
    )


@pytest.mark.asyncio
@patch("app.api.seo.SEOAgentService")
@patch("app.core.security.UserRepository.get_by_id")
async def test_admin_can_access_seo_audit(
    get_user: MagicMock,
    seo_class: MagicMock,
) -> None:
    get_user.return_value = admin()
    seo_class.return_value.audit = AsyncMock(
        return_value=await SEOAgentService(
            AsyncMock(),
            product_repository=FakeProductRepository(),  # type: ignore[arg-type]
        ).audit()
    )
    token = create_access_token(user_id=1, role="admin", token_version=1)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/admin/ai/seo/audit",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["summary"]["products"] == 1


@pytest.mark.asyncio
@patch("app.services.orchestrator_service.SEOAgentService")
async def test_orchestrator_routes_admin_to_seo(
    seo_class: MagicMock,
) -> None:
    report = await SEOAgentService(
        AsyncMock(),
        product_repository=FakeProductRepository(),  # type: ignore[arg-type]
    ).audit()
    seo_class.return_value.audit = AsyncMock(return_value=report)
    service = OrchestratorService(session=AsyncMock(), user=admin())
    result = await service.execute(
        OrchestratorRequest(message="Audit SEO", task_type="seo")
    )
    assert result.detected_intent == "seo"
    assert result.selected_agents == ["seo"]
    assert result.results[0].data["read_only"] is True

