"""Tests for the AI Orchestrator — Step 1 (Product + Recommendation)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.schemas.orchestrator import (
    AgentResult,
    OrchestratorContext,
    OrchestratorRequest,
    OrchestratorResponse,
    OrchestratorTaskType,
)
from app.services.orchestrator_service import (
    OrchestratorService,
    _extract_objective,
    _extract_price,
    _normalize,
)
from app.services.safety_agent import SafetyAgentService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_user(user_id: int = 1, role: str = "customer") -> User:
    user = MagicMock(spec=User)
    user.id = user_id
    user.role = role
    user.is_active = True
    return user


def _fake_session() -> AsyncMock:
    return AsyncMock()


def _product_suggestion_response() -> MagicMock:
    """Mimics a ProductAISuggestionResponse.model_dump(mode='json')."""
    mock = MagicMock()
    mock.model_dump.return_value = {
        "product_id": 42,
        "model": "test-model",
        "cached": True,
        "description": "A test product description that is long enough.",
        "category": "Creatine",
        "seo_title": "Creatine Test Product",
        "seo_description": "Discover this creatine product for your routine.",
        "seo_keywords": ["creatine", "sport", "nutrition"],
        "tags": ["creatine", "sport"],
    }
    return mock


def _recommendation_response(context: str = "product") -> MagicMock:
    """Mimics a RecommendationResponse.model_dump(mode='json')."""
    mock = MagicMock()
    mock.model_dump.return_value = {
        "context": context,
        "strategy": "catalogue",
        "personalized": False,
        "items": [
            {
                "product": {
                    "product_id": 10,
                    "name": "Creatine Monohydrate",
                    "brand": "NUTRIFIT",
                    "category": "Creatine",
                    "price": 250,
                    "currency": "MAD",
                    "stock": 15,
                },
                "score": 0.85,
                "reasons": ["Meme categorie: Creatine"],
            }
        ],
        "disclaimer": "Suggestions informatives basees sur le catalogue.",
    }
    return mock


def _safety_assessment(status: str = "safe") -> MagicMock:
    mock = MagicMock()
    risk_level = {
        "safe": "low",
        "warning": "medium",
        "blocked": "high",
    }[status]
    mock.model_dump.return_value = {
        "status": status,
        "risk_level": risk_level,
        "reasons": (
            ["Aucun risque evident detecte."]
            if status == "safe"
            else ["Medical claim detected."]
        ),
        "recommendations": ["Human validation before publication."],
        "matched_rules": (
            [] if status == "safe" else ["medical_cure"]
        ),
        "model": "rules",
    }
    return mock


@pytest.fixture(autouse=True)
def _mock_orchestrator_safety() -> Any:
    with patch(
        "app.services.orchestrator_service.SafetyAgentService",
        autospec=True,
    ) as mock_safety_cls:
        mock_safety_cls.return_value.assess = AsyncMock(
            return_value=_safety_assessment()
        )
        yield mock_safety_cls


# ---------------------------------------------------------------------------
# Unit tests: intent detection helpers
# ---------------------------------------------------------------------------

class TestNormalizeHelpers:

    def test_normalize_strips_accents(self) -> None:
        assert _normalize("Protéines") == "proteines"

    def test_extract_price_darija(self) -> None:
        assert _extract_price("ta7t 300 MAD") == 300.0

    def test_extract_price_french(self) -> None:
        assert _extract_price("moins de 250") == 250.0

    def test_extract_price_none(self) -> None:
        assert _extract_price("show me products") is None

    def test_extract_objective_creatine(self) -> None:
        assert _extract_objective("bghit creatine") == "creatine"

    def test_extract_objective_none(self) -> None:
        assert _extract_objective("hello world") is None


# ---------------------------------------------------------------------------
# Unit tests: mutation detection
# ---------------------------------------------------------------------------

class TestMutationDetection:

    def test_read_request_is_not_mutation(self) -> None:
        svc = OrchestratorService()
        assert not svc._is_mutation("show me products")
        assert not svc._is_mutation("bghit creatine ta7t 300")

    def test_create_is_mutation(self) -> None:
        svc = OrchestratorService()
        assert svc._is_mutation("create a new product")

    def test_supprimer_is_mutation(self) -> None:
        svc = OrchestratorService()
        assert svc._is_mutation("supprimer le produit 42")

    def test_zid_is_mutation(self) -> None:
        svc = OrchestratorService()
        assert svc._is_mutation("zid product jdid")


# ---------------------------------------------------------------------------
# Unit tests: intent detection
# ---------------------------------------------------------------------------

class TestIntentDetection:

    def test_explicit_product_task_type(self) -> None:
        svc = OrchestratorService()
        intent = svc._detect_domain_intent(
            "anything", OrchestratorTaskType.product
        )
        assert intent == "product"

    def test_explicit_recommendation_task_type(self) -> None:
        svc = OrchestratorService()
        intent = svc._detect_domain_intent(
            "anything", OrchestratorTaskType.recommendation
        )
        assert intent == "recommendation"

    def test_product_keyword(self) -> None:
        svc = OrchestratorService()
        intent = svc._detect_domain_intent(
            "show me the product details", None
        )
        assert intent == "product"

    def test_recommendation_keyword(self) -> None:
        svc = OrchestratorService()
        intent = svc._detect_domain_intent("recommend something", None)
        assert intent == "recommendation"

    def test_content_keyword(self) -> None:
        svc = OrchestratorService()
        intent = svc._detect_domain_intent("kteb description produit", None)
        assert intent == "content"

    def test_marketing_keyword(self) -> None:
        svc = OrchestratorService()
        intent = svc._detect_domain_intent("generate promotion campaign", None)
        assert intent == "marketing"

    def test_darija_bghit_is_recommendation(self) -> None:
        svc = OrchestratorService()
        intent = svc._detect_domain_intent(
            "bghit creatine", None
        )
        assert intent == "recommendation"

    def test_compound_detection(self) -> None:
        svc = OrchestratorService()
        intent = svc._detect_domain_intent(
            "product details and recommend similar", None
        )
        assert intent == "compound"

    def test_objective_only_is_recommendation(self) -> None:
        svc = OrchestratorService()
        intent = svc._detect_domain_intent(
            "creatine", None
        )
        assert intent == "recommendation"


# ---------------------------------------------------------------------------
# Validated context
# ---------------------------------------------------------------------------

class TestContextValidation:

    def test_valid_context(self) -> None:
        ctx = OrchestratorContext(product_id=1, limit=4)
        assert ctx.product_id == 1
        assert ctx.limit == 4

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown context fields"):
            OrchestratorContext.model_validate({"product_id": 1, "bad_key": 5})

    def test_negative_product_id_rejected(self) -> None:
        with pytest.raises(Exception):
            OrchestratorContext(product_id=-1)

    def test_limit_too_high_rejected(self) -> None:
        with pytest.raises(Exception):
            OrchestratorContext(limit=100)

    def test_invalid_content_type_rejected(self) -> None:
        with pytest.raises(Exception):
            OrchestratorContext.model_validate({"content_type": "invalid_type"})

    def test_invalid_channel_rejected(self) -> None:
        with pytest.raises(Exception):
            OrchestratorContext.model_validate({"channels": ["invalid_channel"]})


# ---------------------------------------------------------------------------
# Integration tests: explicit product with product_id
# ---------------------------------------------------------------------------

class TestExplicitProduct:

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.ProductAgentService",
        autospec=True,
    )
    async def test_product_with_product_id(
        self, mock_product_cls: MagicMock
    ) -> None:
        mock_instance = mock_product_cls.return_value
        mock_instance.suggest = AsyncMock(
            return_value=_product_suggestion_response()
        )

        svc = OrchestratorService(
            session=_fake_session(), user=_fake_user()
        )
        request = OrchestratorRequest(
            message="show me product details",
            task_type=OrchestratorTaskType.product,
            context=OrchestratorContext(product_id=42),
        )
        response = await svc.execute(request)

        assert response.detected_intent == "product"
        assert response.selected_agents == ["product", "safety"]
        assert len(response.results) == 2
        assert response.results[0].agent == "product"
        assert response.results[0].status == "success"
        assert response.results[0].data["product_id"] == 42
        assert response.requires_confirmation is False
        mock_instance.suggest.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    async def test_product_without_product_id_is_skipped(self) -> None:
        svc = OrchestratorService(
            session=_fake_session(), user=_fake_user()
        )
        request = OrchestratorRequest(
            message="show me product details",
            task_type=OrchestratorTaskType.product,
        )
        response = await svc.execute(request)

        assert response.detected_intent == "product"
        assert response.results[0].status == "skipped"
        assert "product_id" in response.results[0].data["reason"]


# ---------------------------------------------------------------------------
# Integration tests: explicit recommendation with product_id
# ---------------------------------------------------------------------------

class TestExplicitRecommendation:

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.RecommendationAgentService",
        autospec=True,
    )
    async def test_recommendation_with_product_id(
        self, mock_rec_cls: MagicMock
    ) -> None:
        mock_instance = mock_rec_cls.return_value
        mock_instance.for_product = AsyncMock(
            return_value=_recommendation_response("product")
        )

        svc = OrchestratorService(
            session=_fake_session(), user=_fake_user()
        )
        request = OrchestratorRequest(
            message="recommend similar",
            task_type=OrchestratorTaskType.recommendation,
            context=OrchestratorContext(product_id=42, limit=3),
        )
        response = await svc.execute(request)

        assert response.detected_intent == "recommendation"
        assert response.selected_agents == ["recommendation", "safety"]
        assert response.results[0].status == "success"
        assert response.results[0].data["context"] == "product"
        assert response.requires_confirmation is False
        mock_instance.for_product.assert_awaited_once_with(42, limit=3)


# ---------------------------------------------------------------------------
# Integration tests: compound Darija creatine/budget request
# ---------------------------------------------------------------------------

class TestCompoundCreatineBudget:

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.RecommendationAgentService",
        autospec=True,
    )
    async def test_darija_creatine_budget(
        self, mock_rec_cls: MagicMock
    ) -> None:
        mock_instance = mock_rec_cls.return_value
        mock_instance.for_cart = AsyncMock(
            return_value=_recommendation_response("cart")
        )

        user = _fake_user(user_id=7)
        session = _fake_session()
        svc = OrchestratorService(session=session, user=user)
        request = OrchestratorRequest(
            message="Bghit creatine ta7t 300 MAD w kayna f stock",
        )
        response = await svc.execute(request)

        assert response.detected_intent == "compound"
        assert response.selected_agents == [
            "product",
            "recommendation",
            "safety",
        ]
        assert response.requires_confirmation is False

        rec_result = next(
            r for r in response.results if r.agent == "recommendation"
        )
        assert rec_result.status == "success"
        assert rec_result.data["context"] == "cart"

        prod_result = next(
            r for r in response.results if r.agent == "product"
        )
        assert prod_result.status == "skipped"

        mock_instance.for_cart.assert_awaited_once()
        call_kwargs = mock_instance.for_cart.call_args
        assert call_kwargs[0][0] == 7  # user_id
        assert call_kwargs[1]["objective"] == "creatine"
        assert call_kwargs[1]["max_price"] == 300.0


# ---------------------------------------------------------------------------
# Integration tests: mutation proposal-only
# ---------------------------------------------------------------------------

class TestMutationProposalOnly:

    @pytest.mark.asyncio
    async def test_mutation_returns_blocked(self) -> None:
        svc = OrchestratorService(
            session=_fake_session(), user=_fake_user()
        )
        request = OrchestratorRequest(
            message="create a new product called Super Whey",
        )
        response = await svc.execute(request)

        assert response.requires_confirmation is True
        assert response.proposed_action is not None
        assert "proposal-only" in response.proposed_action
        assert response.results[0].status == "blocked"
        assert "no data was modified" in response.results[0].data["reason"].lower()

    @pytest.mark.asyncio
    async def test_mutation_with_confirm_still_blocked(self) -> None:
        svc = OrchestratorService(
            session=_fake_session(), user=_fake_user()
        )
        request = OrchestratorRequest(
            message="supprimer le produit 42",
            confirm_action=True,
        )
        response = await svc.execute(request)

        assert response.requires_confirmation is True
        assert response.results[0].status == "blocked"

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.RecommendationAgentService",
        autospec=True,
    )
    async def test_requires_confirmation_not_equal_confirm_action(
        self, mock_rec_cls: MagicMock
    ) -> None:
        """Bug fix: requires_confirmation must depend on the message,
        not on confirm_action."""
        mock_instance = mock_rec_cls.return_value
        mock_instance.for_cart = AsyncMock(
            return_value=_recommendation_response("cart")
        )

        svc = OrchestratorService(
            session=_fake_session(), user=_fake_user()
        )

        read_request = OrchestratorRequest(
            message="recommend creatine",
            confirm_action=True,
        )
        response = await svc.execute(read_request)
        assert response.requires_confirmation is False


# ---------------------------------------------------------------------------
# Integration tests: invalid context
# ---------------------------------------------------------------------------

class TestInvalidContext:

    def test_unknown_context_key_returns_422(self) -> None:
        with pytest.raises(Exception):
            OrchestratorRequest(
                message="test",
                context={"unknown_key": "value"},
            )

    def test_negative_product_id_in_context(self) -> None:
        with pytest.raises(Exception):
            OrchestratorRequest(
                message="test",
                context={"product_id": -5},
            )

    def test_limit_above_maximum(self) -> None:
        with pytest.raises(Exception):
            OrchestratorRequest(
                message="test",
                context={"limit": 99},
            )


# ---------------------------------------------------------------------------
# Integration tests: partial failure
# ---------------------------------------------------------------------------

class TestPartialFailure:

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.ProductAgentService",
        autospec=True,
    )
    async def test_product_agent_error_returns_error_result(
        self, mock_product_cls: MagicMock
    ) -> None:
        mock_instance = mock_product_cls.return_value
        mock_instance.suggest = AsyncMock(
            side_effect=HTTPException(
                status_code=503, detail="Ollama unavailable"
            )
        )

        svc = OrchestratorService(
            session=_fake_session(), user=_fake_user()
        )
        request = OrchestratorRequest(
            message="show product info",
            task_type=OrchestratorTaskType.product,
            context=OrchestratorContext(product_id=99),
        )
        response = await svc.execute(request)

        assert response.results[0].status == "error"
        assert response.results[0].data["error"] == "Ollama unavailable"
        assert response.results[0].data["status_code"] == 503

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.RecommendationAgentService",
        autospec=True,
    )
    async def test_recommendation_agent_error_returns_error_result(
        self, mock_rec_cls: MagicMock
    ) -> None:
        mock_instance = mock_rec_cls.return_value
        mock_instance.for_product = AsyncMock(
            side_effect=HTTPException(
                status_code=404, detail="Product not found"
            )
        )

        svc = OrchestratorService(
            session=_fake_session(), user=_fake_user()
        )
        request = OrchestratorRequest(
            message="recommend similar",
            task_type=OrchestratorTaskType.recommendation,
            context=OrchestratorContext(product_id=999),
        )
        response = await svc.execute(request)

        assert response.results[0].status == "error"
        assert "not found" in response.results[0].data["error"].lower()


# ---------------------------------------------------------------------------
# No fabricated results
# ---------------------------------------------------------------------------

class TestNoFabricatedResults:

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.ProductAgentService",
        autospec=True,
    )
    async def test_product_result_comes_from_mock(
        self, mock_product_cls: MagicMock
    ) -> None:
        """The data returned must be exactly what the mock returns."""
        mock_response = _product_suggestion_response()
        expected_data = mock_response.model_dump.return_value

        mock_instance = mock_product_cls.return_value
        mock_instance.suggest = AsyncMock(return_value=mock_response)

        svc = OrchestratorService(
            session=_fake_session(), user=_fake_user()
        )
        request = OrchestratorRequest(
            message="fiche produit",
            task_type=OrchestratorTaskType.product,
            context=OrchestratorContext(product_id=42),
        )
        response = await svc.execute(request)

        assert response.results[0].data == expected_data
        mock_response.model_dump.assert_called_once_with(mode="json")

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.RecommendationAgentService",
        autospec=True,
    )
    async def test_recommendation_result_comes_from_mock(
        self, mock_rec_cls: MagicMock
    ) -> None:
        mock_response = _recommendation_response("cart")
        expected_data = mock_response.model_dump.return_value

        mock_instance = mock_rec_cls.return_value
        mock_instance.for_cart = AsyncMock(return_value=mock_response)

        user = _fake_user(user_id=3)
        svc = OrchestratorService(session=_fake_session(), user=user)
        request = OrchestratorRequest(
            message="bghit creatine ta7t 300",
        )
        response = await svc.execute(request)

        rec_result = next(
            r for r in response.results if r.agent == "recommendation"
        )
        assert rec_result.data == expected_data
        mock_response.model_dump.assert_called_once_with(mode="json")


# ---------------------------------------------------------------------------
# Safety Agent integration
# ---------------------------------------------------------------------------

class TestSafetyIntegration:

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.RecommendationAgentService",
        autospec=True,
    )
    async def test_safe_result_is_assessed(
        self,
        mock_rec_cls: MagicMock,
        _mock_orchestrator_safety: MagicMock,
    ) -> None:
        mock_rec_cls.return_value.for_cart = AsyncMock(
            return_value=_recommendation_response("cart")
        )
        service = OrchestratorService(
            session=_fake_session(),
            user=_fake_user(),
        )

        response = await service.execute(
            OrchestratorRequest(message="bghit creatine ta7t 300")
        )

        assert response.selected_agents == [
            "product",
            "recommendation",
            "safety",
        ]
        safety = next(
            result for result in response.results
            if result.agent == "safety"
        )
        assert safety.data["status"] == "safe"
        assert response.requires_confirmation is False
        _mock_orchestrator_safety.return_value.assess.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.RecommendationAgentService",
        autospec=True,
    )
    async def test_blocked_safety_requires_human_review(
        self,
        mock_rec_cls: MagicMock,
        _mock_orchestrator_safety: MagicMock,
    ) -> None:
        mock_rec_cls.return_value.for_cart = AsyncMock(
            return_value=_recommendation_response("cart")
        )
        _mock_orchestrator_safety.return_value.assess = AsyncMock(
            return_value=_safety_assessment("blocked")
        )
        service = OrchestratorService(
            session=_fake_session(),
            user=_fake_user(),
        )

        response = await service.execute(
            OrchestratorRequest(
                message="bghit produit kayguerit diabete"
            )
        )

        assert response.requires_confirmation is True
        assert response.proposed_action is not None
        safety = next(
            result for result in response.results
            if result.agent == "safety"
        )
        assert safety.data["status"] == "blocked"

    @pytest.mark.asyncio
    @patch(
        "app.services.orchestrator_service.RecommendationAgentService",
        autospec=True,
    )
    async def test_safety_failure_fails_closed(
        self,
        mock_rec_cls: MagicMock,
        _mock_orchestrator_safety: MagicMock,
    ) -> None:
        mock_rec_cls.return_value.for_cart = AsyncMock(
            return_value=_recommendation_response("cart")
        )
        _mock_orchestrator_safety.return_value.assess = AsyncMock(
            side_effect=RuntimeError("unavailable")
        )
        service = OrchestratorService(
            session=_fake_session(),
            user=_fake_user(),
        )

        response = await service.execute(
            OrchestratorRequest(message="recommend creatine")
        )

        assert response.requires_confirmation is True
        safety = next(
            result for result in response.results
            if result.agent == "safety"
        )
        assert safety.status == "error"
        assert safety.data["status"] == "warning"

    @pytest.mark.asyncio
    async def test_read_only_assessment_does_not_persist(self) -> None:
        session = MagicMock()
        service = SafetyAgentService(session)

        assessment = await service.assess(
            "Description factuelle de creatine.",
            use_ai=False,
        )

        assert assessment.status == "safe"
        assert assessment.model == "rules"
        session.add.assert_not_called()
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Integration tests: FastAPI endpoints
# ---------------------------------------------------------------------------

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token

class TestAPIEndpoints:

    @pytest.mark.asyncio
    async def test_unauthenticated_rejected(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/orchestrator/execute",
                json={"message": "recommend creatine"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.orchestrator.OrchestratorService")
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_authenticated_customer_access(
        self, mock_get_by_id: MagicMock, mock_svc_cls: MagicMock
    ) -> None:
        mock_get_by_id.return_value = User(id=1, role="customer", token_version=1, is_active=True)
        mock_instance = mock_svc_cls.return_value
        mock_instance.execute = AsyncMock(
            return_value=OrchestratorResponse(
                detected_intent="recommendation",
                selected_agents=["recommendation"],
                results=[],
                requires_confirmation=False,
                proposed_action=None,
            )
        )
        token = create_access_token(user_id=1, role="customer", token_version=1)
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/orchestrator/execute",
                headers=headers,
                json={"message": "recommend creatine"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_invalid_context_returns_422(self, mock_get_by_id: MagicMock) -> None:
        mock_get_by_id.return_value = User(id=1, role="customer", token_version=1, is_active=True)
        token = create_access_token(user_id=1, role="customer", token_version=1)
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/orchestrator/execute",
                headers=headers,
                json={
                    "message": "recommend creatine",
                    "context": {"invalid_key": "bad"},
                },
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    @patch("app.api.orchestrator.OrchestratorService")
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_mutation_no_agent_call(
        self, mock_get_by_id: MagicMock, mock_svc_cls: MagicMock
    ) -> None:
        mock_get_by_id.return_value = User(id=1, role="customer", token_version=1, is_active=True)
        mock_instance = mock_svc_cls.return_value
        mock_instance.execute = AsyncMock(
            return_value=OrchestratorResponse(
                detected_intent="product",
                selected_agents=["product"],
                results=[],
                requires_confirmation=True,
                proposed_action="proposal-only",
            )
        )
        token = create_access_token(user_id=1, role="customer", token_version=1)
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/orchestrator/execute",
                headers=headers,
                json={"message": "supprimer ce produit"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["requires_confirmation"] is True
        mock_instance.execute.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.api.orchestrator.OrchestratorService")
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_exact_creatine_budget_request(
        self, mock_get_by_id: MagicMock, mock_svc_cls: MagicMock
    ) -> None:
        mock_get_by_id.return_value = User(id=1, role="customer", token_version=1, is_active=True)
        """Tests that the endpoint passes the message correctly to the service."""
        mock_instance = mock_svc_cls.return_value
        mock_instance.execute = AsyncMock(
            return_value=OrchestratorResponse(
                detected_intent="compound",
                selected_agents=["product", "recommendation"],
                results=[],
                requires_confirmation=False,
                proposed_action=None,
            )
        )
        token = create_access_token(user_id=1, role="customer", token_version=1)
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/orchestrator/execute",
                headers=headers,
                json={"message": "Bghit creatine ta7t 300 MAD w kayna f stock"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["detected_intent"] == "compound"
        assert data["selected_agents"] == ["product", "recommendation"]

    @pytest.mark.asyncio
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_empty_message_returns_422(self, mock_get_by_id: MagicMock) -> None:
        mock_get_by_id.return_value = User(id=1, role="customer", token_version=1, is_active=True)
        token = create_access_token(user_id=1, role="customer", token_version=1)
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/orchestrator/execute",
                headers=headers,
                json={"message": "   "},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    @patch("app.api.orchestrator.OrchestratorService")
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_admin_content_preview_allowed(
        self, mock_get_by_id: MagicMock, mock_svc_cls: MagicMock
    ) -> None:
        mock_get_by_id.return_value = User(id=1, role="admin", token_version=1, is_active=True)
        mock_instance = mock_svc_cls.return_value
        mock_instance.execute = AsyncMock(
            return_value=OrchestratorResponse(
                detected_intent="content",
                selected_agents=["content"],
                results=[],
                requires_confirmation=False,
                proposed_action=None,
            )
        )
        token = create_access_token(user_id=1, role="admin", token_version=1)
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/orchestrator/execute",
                headers=headers,
                json={"message": "cree un contenu sur la whey", "task_type": "content"},
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_customer_content_preview_forbidden(
        self, mock_get_by_id: MagicMock
    ) -> None:
        mock_get_by_id.return_value = User(id=1, role="customer", token_version=1, is_active=True)
        token = create_access_token(user_id=1, role="customer", token_version=1)
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/orchestrator/execute",
                headers=headers,
                json={"message": "cree un contenu sur la whey", "task_type": "content"},
            )
        assert response.status_code == 403


    @pytest.mark.asyncio
    @patch("app.api.orchestrator.OperationsRepository")
    @patch("app.api.orchestrator.OrchestratorService")
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_execute_adds_orchestrator_history(
        self,
        mock_get_by_id: MagicMock,
        mock_svc_cls: MagicMock,
        mock_operations_cls: MagicMock,
    ) -> None:
        mock_get_by_id.return_value = User(
            id=7,
            email="client@nutrifit.ma",
            role="customer",
            token_version=1,
            is_active=True,
        )
        result = OrchestratorResponse(
            detected_intent="recommendation",
            selected_agents=["recommendation", "safety"],
            results=[],
            requires_confirmation=False,
            proposed_action=None,
        )
        mock_svc_cls.return_value.execute = AsyncMock(return_value=result)
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
                "/api/orchestrator/execute",
                headers={"Authorization": f"Bearer {token}"},
                json={"message": "9ter7 lia creatine"},
            )

        assert response.status_code == 200
        history_payload = (
            mock_operations_cls.return_value.add_audit.call_args.kwargs
        )
        assert history_payload["actor_id"] == 7
        assert history_payload["entity_type"] == "ai_orchestrator"
        assert history_payload["details"]["message"] == "9ter7 lia creatine"
        assert history_payload["details"]["selected_agents"] == [
            "recommendation",
            "safety",
        ]

    @pytest.mark.asyncio
    @patch("app.api.orchestrator.OperationsRepository")
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_admin_can_list_orchestrator_history(
        self,
        mock_get_by_id: MagicMock,
        mock_operations_cls: MagicMock,
    ) -> None:
        mock_get_by_id.return_value = User(
            id=1,
            email="admin@nutrifit.ma",
            role="admin",
            token_version=1,
            is_active=True,
        )
        log = MagicMock()
        log.id = 15
        log.actor_id = 7
        log.actor_role = "customer"
        log.created_at = datetime.now(UTC)
        log.details = json.dumps(
            {
                "message": "bghit creatine",
                "detected_intent": "recommendation",
                "selected_agents": ["recommendation", "safety"],
                "results": [],
                "requires_confirmation": False,
                "proposed_action": None,
            }
        )
        mock_operations_cls.return_value.list_orchestrator_runs = AsyncMock(
            return_value=([(log, "client@nutrifit.ma")], 1)
        )
        token = create_access_token(
            user_id=1,
            role="admin",
            token_version=1,
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/orchestrator/history",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["actor_email"] == "client@nutrifit.ma"
        assert payload["items"][0]["message"] == "bghit creatine"

    @pytest.mark.asyncio
    @patch("app.core.security.UserRepository.get_by_id")
    async def test_customer_cannot_list_orchestrator_history(
        self,
        mock_get_by_id: MagicMock,
    ) -> None:
        mock_get_by_id.return_value = User(
            id=7,
            email="client@nutrifit.ma",
            role="customer",
            token_version=1,
            is_active=True,
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
            response = await client.get(
                "/api/orchestrator/history",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 403


class TestContentMarketingAgents:

    @pytest.mark.asyncio
    @patch("app.services.orchestrator_service.ContentAgentService")
    async def test_explicit_content_preview(self, mock_content_cls: MagicMock) -> None:
        mock_instance = mock_content_cls.return_value
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"title": "Test"}
        mock_instance.preview = AsyncMock(return_value=mock_result)
        
        svc = OrchestratorService(session=_fake_session(), user=_fake_user(role="admin"))
        request = OrchestratorRequest(
            message="cree contenu",
            task_type=OrchestratorTaskType.content,
        )
        response = await svc.execute(request)
        
        assert response.detected_intent == "content"
        assert response.selected_agents == ["content", "safety"]
        mock_instance.preview.assert_awaited_once()
        req_arg = mock_instance.preview.call_args[0][0]
        assert req_arg.content_type == "promotion"

    @pytest.mark.asyncio
    @patch("app.services.orchestrator_service.MarketingAgentService")
    async def test_explicit_marketing_preview(self, mock_marketing_cls: MagicMock) -> None:
        mock_instance = mock_marketing_cls.return_value
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"campaign_title": "Test"}
        mock_instance.preview = AsyncMock(return_value=mock_result)
        
        svc = OrchestratorService(session=_fake_session(), user=_fake_user(role="admin"))
        request = OrchestratorRequest(
            message="cree campagne",
            task_type=OrchestratorTaskType.marketing,
        )
        response = await svc.execute(request)
        
        assert response.detected_intent == "marketing"
        assert response.selected_agents == ["marketing", "safety"]
        mock_instance.preview.assert_awaited_once()
        req_arg = mock_instance.preview.call_args[0][0]
        assert req_arg.campaign_type == "promotion"

    @pytest.mark.asyncio
    async def test_customer_receives_403(self) -> None:
        svc = OrchestratorService(session=_fake_session(), user=_fake_user(role="customer"))
        request = OrchestratorRequest(message="cree contenu", task_type=OrchestratorTaskType.content)
        with pytest.raises(HTTPException) as exc:
            await svc.execute(request)
        assert exc.value.status_code == 403

        request2 = OrchestratorRequest(message="cree marketing", task_type=OrchestratorTaskType.marketing)
        with pytest.raises(HTTPException) as exc:
            await svc.execute(request2)
        assert exc.value.status_code == 403
