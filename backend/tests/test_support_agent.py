from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.schemas.orchestrator import OrchestratorRequest
from app.schemas.support_agent import SupportAgentRequest, SupportAgentResponse
from app.services.orchestrator_service import OrchestratorService
from app.services.support_agent import SupportAgentService


def customer(user_id: int = 7) -> User:
    return User(
        id=user_id,
        email=f"client-{user_id}@example.com",
        hashed_password="test",
        role="customer",
        token_version=1,
        is_active=True,
    )


def order(
    order_id: int = 42,
    *,
    user_id: int = 7,
    status: str = "shipped",
) -> MagicMock:
    value = MagicMock()
    value.id = order_id
    value.user_id = user_id
    value.order_status = status
    value.payment_method = "cash_on_delivery"
    value.payment_status = "pending"
    value.total = 349.9
    value.currency = "MAD"
    return value


class FakeOrderRepository:
    def __init__(self, orders: list[MagicMock] | None = None) -> None:
        self.orders = orders or []

    async def get_by_id(
        self,
        order_id: int,
        *,
        user_id: int | None = None,
    ) -> MagicMock | None:
        return next(
            (
                value
                for value in self.orders
                if value.id == order_id and value.user_id == user_id
            ),
            None,
        )

    async def list_orders(self, **_: object) -> tuple[list[MagicMock], int]:
        return self.orders[:1], len(self.orders)


class FakeProductRepository:
    def __init__(self) -> None:
        self.product = {
            "product_id": 20,
            "name": "Creatine Monohydrate",
            "brand": "NUTRIFIT",
            "category": "Créatine",
            "price": 249.0,
            "currency": "MAD",
            "stock": 14,
            "ingredients": [{"name": "Créatine monohydrate"}],
            "is_active": True,
        }

    async def get_by_product_id(self, product_id: int) -> dict | None:
        return self.product if product_id == 20 else None

    async def list_products(self, **_: object) -> tuple[list[dict], int]:
        return [self.product], 1


def service(
    *,
    orders: list[MagicMock] | None = None,
) -> SupportAgentService:
    return SupportAgentService(
        AsyncMock(),
        customer(),
        order_repository=FakeOrderRepository(orders),  # type: ignore[arg-type]
        product_repository=FakeProductRepository(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_medical_question_is_stopped_without_ai_generation() -> None:
    support = service()
    support._generate_answer = AsyncMock()  # type: ignore[method-assign]

    result = await support.preview(
        SupportAgentRequest(
            message="Je suis enceinte, est-ce que cette créatine me convient ?"
        )
    )

    assert result.topic == "medical_safety"
    assert result.safety_notice
    assert "médecin" in result.answer
    support._generate_answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_customer_receives_only_owned_order_status() -> None:
    support = service(orders=[order()])

    result = await support.preview(
        SupportAgentRequest(message="Où est ma commande 42 ?"),
        use_ai=False,
    )

    assert result.topic == "order"
    assert result.order is not None
    assert result.order.order_id == 42
    assert result.order.order_status_label == "Expédiée"
    assert result.read_only is True


@pytest.mark.asyncio
async def test_darija_misspelled_delayed_order_uses_latest_owned_order() -> None:
    support = service(orders=[order(status="preparing")])

    result = await support.preview(
        SupportAgentRequest(message="l commende t3atlat 3liya"),
        use_ai=False,
    )

    assert result.topic == "order"
    assert result.order is not None
    assert result.order.order_id == 42
    assert result.order.order_status_label == "En préparation"


@pytest.mark.asyncio
async def test_unknown_or_unowned_order_is_not_exposed() -> None:
    support = service(orders=[order(order_id=99, user_id=8)])

    result = await support.preview(
        SupportAgentRequest(message="Où est ma commande 99 ?"),
        use_ai=False,
    )

    assert result.order is None
    assert result.needs_human is True
    assert result.support_url == "/help"


@pytest.mark.asyncio
async def test_payment_answer_uses_local_site_rules() -> None:
    result = await service().preview(
        SupportAgentRequest(
            message="Comment fonctionne le paiement à la livraison ?"
        ),
        use_ai=False,
    )

    assert result.topic == "payment"
    assert "paiement à la livraison" in result.answer
    assert result.needs_human is False


@pytest.mark.asyncio
async def test_product_answer_is_grounded_in_catalogue() -> None:
    result = await service().preview(
        SupportAgentRequest(
            message="Quels sont les ingrédients de la creatine ?"
        ),
        use_ai=False,
    )

    assert result.topic == "product"
    assert result.product is not None
    assert result.product.product_id == 20
    assert "Créatine monohydrate" in result.answer


def test_orchestrator_detects_support_intent_before_product_intent() -> None:
    support = OrchestratorService()
    assert (
        support._detect_domain_intent(
            "J'ai un problème avec la livraison de mon produit",
            None,
        )
        == "support"
    )


def test_orchestrator_understands_darija_delayed_order_typo() -> None:
    support = OrchestratorService()
    assert (
        support._detect_domain_intent(
            "l commende t3atlat 3liya",
            None,
        )
        == "support"
    )


@pytest.mark.asyncio
@patch("app.services.orchestrator_service.SupportAgentService")
async def test_orchestrator_routes_customer_to_support(
    support_class: MagicMock,
) -> None:
    preview = SupportAgentResponse(
        topic="payment",
        answer="Le paiement à la livraison est disponible.",
        needs_human=False,
        model="règles du site",
    )
    support_class.return_value.preview = AsyncMock(return_value=preview)
    orchestrator = OrchestratorService(
        session=AsyncMock(),
        user=customer(),
    )
    orchestrator._run_safety = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = await orchestrator.execute(
        OrchestratorRequest(
            message="Comment fonctionne le paiement à la livraison ?",
        )
    )

    assert result.detected_intent == "support"
    assert result.selected_agents == ["support"]
    assert result.results[0].data["read_only"] is True
    support_class.return_value.preview.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.services.orchestrator_service.SupportAgentService")
async def test_support_result_does_not_run_duplicate_orchestrator_safety(
    support_class: MagicMock,
) -> None:
    support_class.return_value.preview = AsyncMock(
        return_value=SupportAgentResponse(
            topic="order",
            answer="Votre commande est en préparation.",
            needs_human=False,
            model="données de commande",
        )
    )
    orchestrator = OrchestratorService(
        session=AsyncMock(),
        user=customer(),
    )
    orchestrator._run_safety = AsyncMock()  # type: ignore[method-assign]

    result = await orchestrator.execute(
        OrchestratorRequest(message="l commende t3atlat 3liya")
    )

    assert result.detected_intent == "support"
    assert result.selected_agents == ["support"]
    assert result.requires_confirmation is False
    orchestrator._run_safety.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.api.support_agent.SupportAgentService")
@patch("app.core.security.UserRepository.get_by_id")
async def test_customer_can_use_direct_support_chat(
    get_user: MagicMock,
    support_class: MagicMock,
) -> None:
    get_user.return_value = customer()
    support_class.return_value.preview = AsyncMock(
        return_value=SupportAgentResponse(
            topic="delivery",
            answer="Livraison partout au Maroc.",
            needs_human=False,
            model="règles du site",
        )
    )
    token = create_access_token(
        user_id=7,
        role="customer",
        token_version=1,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/support/ai/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Comment fonctionne la livraison ?"},
        )

    assert response.status_code == 200
    assert response.json()["topic"] == "delivery"
    support_class.return_value.preview.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.core.security.UserRepository.get_by_id")
async def test_staff_account_cannot_impersonate_customer_support_chat(
    get_user: MagicMock,
) -> None:
    get_user.return_value = User(
        id=3,
        email="support@example.com",
        hashed_password="test",
        role="support",
        token_version=1,
        is_active=True,
    )
    token = create_access_token(
        user_id=3,
        role="support",
        token_version=1,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/support/ai/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Où est ma commande ?"},
        )

    assert response.status_code == 403
