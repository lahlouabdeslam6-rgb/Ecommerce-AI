from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.orchestrator import (
    AgentResult,
    OrchestratorContext,
    OrchestratorRequest,
    OrchestratorResponse,
    OrchestratorTaskType,
)
from app.services.product_agent import ProductAgentService
from app.services.recommendation_agent import RecommendationAgentService
from app.services.safety_agent import SafetyAgentService
from app.services.content_agent import ContentAgentService
from app.services.marketing_agent import MarketingAgentService
from app.services.analytics_agent import AnalyticsAgentService
from app.services.stock_forecast_agent import StockForecastAgentService
from app.services.support_agent import SupportAgentService
from app.schemas.content import ContentGenerateRequest
from app.schemas.marketing import MarketingGenerateRequest
from app.schemas.support_agent import SupportAgentRequest
from pydantic import ValidationError


logger = logging.getLogger("nutrifit.orchestrator")
SAFETY_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Mutation verb detection  (EN / FR / Darija-Latin)
# ---------------------------------------------------------------------------
_MUTATION_VERBS: set[str] = {
    # English
    "create", "add", "update", "modify", "change", "edit",
    "delete", "remove", "destroy", "publish", "unpublish",
    "approve", "reject", "send", "cancel", "activate", "deactivate",
    # French
    "creer", "ajouter", "modifier", "changer", "supprimer",
    "effacer", "publier", "depublier", "approuver", "rejeter",
    "envoyer", "annuler", "activer", "desactiver",
    # Darija (Latin script)
    "zid", "bddel", "7yyed", "msa7",
}

# ---------------------------------------------------------------------------
# Intent keyword map  (EN / FR / Darija-Latin)
# ---------------------------------------------------------------------------
_INTENT_KEYWORDS: dict[str, set[str]] = {
    "support": {
        "support", "aide", "livraison", "livrer", "retour",
        "remboursement", "commande", "colis", "paiement", "cod",
        "retard", "reclamation", "probleme", "tracking", "suivi",
    },
    "product": {
        # EN
        "product", "catalogue", "catalog", "item", "detail",
        "description", "category", "ingredient",
        # FR
        "produit", "fiche", "categorie",
        # Darija
        "sle3a", "monta9a", "montaj",
    },
    "recommendation": {
        # EN
        "recommend", "recommendation", "suggest", "suggestion",
        "similar", "alternative", "budget",
        # FR
        "recommandation", "recommander", "similaire", "suggestion",
        "suggerer", "alternative",
        # Darija
        "bghit", "3tini", "9ter7", "chno", "wash",
    },
    "content": {
        "content", "contenu", "description", "texte", "kteb"
    },
    "marketing": {
        "marketing", "campagne", "campaign", "promotion", "promo", "email"
    },
    "analytics": {
        "analytics", "analytique", "analyse", "ventes", "vente", "revenu",
        "revenue", "statistiques", "performance", "chiffre", "dashboard",
    },
    "stock_forecast": {
        "forecast", "prevision", "rupture", "reapprovisionnement",
        "approvisionnement", "epuisement",
    },
}


def _normalize(text: str) -> str:
    """Strip accents and collapse whitespace to lowercase."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _extract_price(text: str) -> float | None:
    """Try to pull a numeric price from Darija/FR patterns like 'ta7t 300'."""
    for pattern in (
        r"(?:ta7t|moins\s*de?|under|below|max|budget)\s+(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*(?:mad|dh|dirhams?)",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _extract_objective(text: str) -> str | None:
    """Extract a plausible product objective from message text."""
    norm = _normalize(text)
    # known supplement categories
    objectives = [
        "creatine", "whey", "proteine", "proteines", "omega",
        "vitamine", "vitamines", "bcaa", "eaa", "pre workout",
        "pre-workout", "gainer", "mass gainer", "collagen",
        "collagene", "magnesium", "zinc", "multivitamin",
    ]
    for obj in objectives:
        if obj in norm:
            return obj
    return None


class OrchestratorService:
    """Routes requests to Product and Recommendation agents.

    This Step-1 implementation handles read-only orchestration.
    Mutation requests are flagged but never executed.
    """

    def __init__(
        self,
        session: AsyncSession | None = None,
        user: User | None = None,
    ) -> None:
        self.session = session
        self.user = user

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def execute(
        self, request: OrchestratorRequest
    ) -> OrchestratorResponse:
        message_normalised = _normalize(request.message)

        # 1. Mutation detection and intent resolution
        is_mutation = self._is_mutation(message_normalised)
        intent = self._detect_domain_intent(
            message_normalised, request.task_type
        )

        # 2. Admin Check for Content/Marketing
        if intent in ("content", "marketing", "analytics", "stock_forecast"):
            if self.user is None or self.user.role != "admin":
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "Les agents Content, Marketing, Analytics et Stock Forecast sont réservés aux administrateurs.",
                )

        proposed_action = (
            self._describe_mutation(request.message)
            if is_mutation
            else None
        )

        if is_mutation and intent not in ("content", "marketing"):
            return OrchestratorResponse(
                detected_intent=intent,
                selected_agents=[intent],
                results=[
                    AgentResult(
                        agent=intent,
                        status="blocked",
                        data={
                            "reason": "Mutation requests are proposal-only "
                            "in this version. No data was modified."
                        },
                    )
                ],
                requires_confirmation=True,
                proposed_action=proposed_action,
            )

        requires_confirmation = is_mutation

        # 3. Resolve context
        ctx = request.context or OrchestratorContext()

        # 4. Dispatch
        if intent == "product":
            results, agents = await self._handle_product(ctx)
        elif intent == "recommendation":
            results, agents = await self._handle_recommendation(
                ctx, message_normalised
            )
        elif intent == "content":
            results, agents = await self._handle_content(ctx, message_normalised)
        elif intent == "marketing":
            results, agents = await self._handle_marketing(ctx, message_normalised)
        elif intent == "analytics":
            results, agents = await self._handle_analytics(ctx)
        elif intent == "stock_forecast":
            results, agents = await self._handle_stock_forecast(ctx)
        elif intent == "support":
            results, agents = await self._handle_support(
                ctx,
                request.message,
            )
        else:
            # Compound: product + recommendation
            results, agents = await self._handle_compound(
                ctx, message_normalised
            )

        safety_result = await self._run_safety(request.message, results)
        if safety_result is not None:
            results.append(safety_result)
            agents.append("safety")
            safety_status = str(safety_result.data.get("status") or "")
            if safety_status in {"warning", "blocked"}:
                requires_confirmation = True
                proposed_action = (
                    "A human safety review is required before this AI result "
                    "can be used."
                )

        return OrchestratorResponse(
            detected_intent=intent,
            selected_agents=agents,
            results=results,
            requires_confirmation=requires_confirmation,
            proposed_action=proposed_action,
        )

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    def _detect_domain_intent(
        self,
        normalised: str,
        explicit: OrchestratorTaskType | None,
    ) -> str:
        if explicit is not None:
            return explicit.value

        tokens = set(re.findall(r"[a-z0-9]+", normalised))

        support_hits = tokens & _INTENT_KEYWORDS["support"]
        if support_hits:
            return "support"

        forecast_hits = tokens & _INTENT_KEYWORDS["stock_forecast"]
        if forecast_hits:
            return "stock_forecast"

        product_hits = tokens & _INTENT_KEYWORDS["product"]
        rec_hits = tokens & _INTENT_KEYWORDS["recommendation"]

        if product_hits and rec_hits:
            return "compound"

        objective = _extract_objective(normalised)
        price = _extract_price(normalised)
        has_stock_or_catalogue = bool(tokens & {"stock", "catalogue", "catalog"})

        if objective and (price is not None or has_stock_or_catalogue):
            return "compound"

        content_hits = tokens & _INTENT_KEYWORDS["content"]
        marketing_hits = tokens & _INTENT_KEYWORDS["marketing"]
        analytics_hits = tokens & _INTENT_KEYWORDS["analytics"]

        if analytics_hits:
            return "analytics"
        if content_hits:
            return "content"
        if marketing_hits:
            return "marketing"

        if product_hits:
            return "product"
        if rec_hits:
            return "recommendation"

        # If a known objective term or price is present without catalogue context, assume recommendation
        if objective or price is not None:
            return "recommendation"

        return "recommendation"  # safe default

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_mutation(normalised: str) -> bool:
        tokens = set(re.findall(r"[a-z0-9]+", normalised))
        return bool(tokens & _MUTATION_VERBS)

    @staticmethod
    def _describe_mutation(raw_message: str) -> str:
        return (
            f"The request appears to modify data: \"{raw_message[:200]}\". "
            "This action is proposal-only and was not executed."
        )

    # ------------------------------------------------------------------
    # Agent dispatchers
    # ------------------------------------------------------------------

    async def _handle_product(
        self, ctx: OrchestratorContext
    ) -> tuple[list[AgentResult], list[str]]:
        if ctx.product_id is None:
            return (
                [
                    AgentResult(
                        agent="product",
                        status="skipped",
                        data={
                            "reason": "product_id is required in context "
                            "for the Product Agent."
                        },
                    )
                ],
                ["product"],
            )

        data = await self._call_product_agent(ctx.product_id)
        return [data], ["product"]

    async def _handle_recommendation(
        self,
        ctx: OrchestratorContext,
        normalised: str,
    ) -> tuple[list[AgentResult], list[str]]:
        if ctx.product_id is not None:
            data = await self._call_recommendation_for_product(
                ctx.product_id, ctx.limit or 4
            )
            return [data], ["recommendation"]

        # Cart-based recommendation
        data = await self._call_recommendation_for_cart(ctx, normalised)
        return [data], ["recommendation"]

    async def _handle_support(
        self,
        ctx: OrchestratorContext,
        raw_message: str,
    ) -> tuple[list[AgentResult], list[str]]:
        if self.session is None or self.user is None:
            return [
                AgentResult(
                    agent="support",
                    status="error",
                    data={"error": "Une session authentifiée est requise."},
                )
            ], ["support"]
        try:
            response = await SupportAgentService(
                self.session,
                self.user,
            ).preview(
                SupportAgentRequest(
                    message=raw_message,
                    order_id=ctx.order_id,
                    product_id=ctx.product_id,
                ),
                use_ai=True,
            )
            return [
                AgentResult(
                    agent="support",
                    status="success",
                    data=response.model_dump(mode="json"),
                )
            ], ["support"]
        except Exception as exc:
            logger.warning("SupportAgent preview error: %s", exc)
            return [
                AgentResult(
                    agent="support",
                    status="error",
                    data={
                        "error": (
                            "Le Support Agent est momentanément indisponible. "
                            "Contactez le support humain."
                        ),
                        "support_url": "/help",
                        "needs_human": True,
                    },
                )
            ], ["support"]

    async def _handle_compound(
        self,
        ctx: OrchestratorContext,
        normalised: str,
    ) -> tuple[list[AgentResult], list[str]]:
        agents: list[str] = ["product", "recommendation"]
        results: list[AgentResult] = []

        # Product leg
        if ctx.product_id is not None:
            results.append(await self._call_product_agent(ctx.product_id))
        else:
            results.append(
                AgentResult(
                    agent="product",
                    status="skipped",
                    data={
                        "reason": "product_id absent; "
                        "Product Agent requires a product_id to run."
                    },
                )
            )

        # Recommendation leg
        if ctx.product_id is not None:
            results.append(
                await self._call_recommendation_for_product(
                    ctx.product_id, ctx.limit or 4
                )
            )
        else:
            results.append(
                await self._call_recommendation_for_cart(ctx, normalised)
            )

        return results, agents

    # ------------------------------------------------------------------
    # Real agent calls
    # ------------------------------------------------------------------

    async def _call_product_agent(self, product_id: int) -> AgentResult:
        try:
            service = ProductAgentService()
            suggestion = await service.suggest(product_id)
            return AgentResult(
                agent="product",
                status="success",
                data=suggestion.model_dump(mode="json"),
            )
        except HTTPException as exc:
            return AgentResult(
                agent="product",
                status="error",
                data={"error": exc.detail, "status_code": exc.status_code},
            )
        except Exception as exc:
            logger.warning("ProductAgent error for %s: %s", product_id, exc)
            return AgentResult(
                agent="product",
                status="error",
                data={"error": str(exc)},
            )

    async def _call_recommendation_for_product(
        self, product_id: int, limit: int
    ) -> AgentResult:
        try:
            service = RecommendationAgentService()
            result = await service.for_product(product_id, limit=limit)
            return AgentResult(
                agent="recommendation",
                status="success",
                data=result.model_dump(mode="json"),
            )
        except HTTPException as exc:
            return AgentResult(
                agent="recommendation",
                status="error",
                data={"error": exc.detail, "status_code": exc.status_code},
            )
        except Exception as exc:
            logger.warning(
                "RecommendationAgent for_product error %s: %s",
                product_id,
                exc,
            )
            return AgentResult(
                agent="recommendation",
                status="error",
                data={"error": str(exc)},
            )

    async def _call_recommendation_for_cart(
        self,
        ctx: OrchestratorContext,
        normalised: str,
    ) -> AgentResult:
        if self.session is None or self.user is None:
            return AgentResult(
                agent="recommendation",
                status="error",
                data={
                    "error": "Cart recommendations require "
                    "an authenticated session."
                },
            )

        objective = ctx.objective or _extract_objective(normalised)
        max_price = ctx.max_price or _extract_price(normalised)
        limit = ctx.limit or 4

        try:
            service = RecommendationAgentService(self.session)
            result = await service.for_cart(
                self.user.id,
                objective=objective,
                max_price=max_price,
                limit=limit,
            )
            return AgentResult(
                agent="recommendation",
                status="success",
                data=result.model_dump(mode="json"),
            )
        except HTTPException as exc:
            return AgentResult(
                agent="recommendation",
                status="error",
                data={"error": exc.detail, "status_code": exc.status_code},
            )
        except Exception as exc:
            logger.warning("RecommendationAgent for_cart error: %s", exc)
            return AgentResult(
                agent="recommendation",
                status="error",
                data={"error": str(exc)},
            )

    async def _run_safety(
        self,
        message: str,
        results: list[AgentResult],
    ) -> AgentResult | None:
        successful = [
            result
            for result in results
            if result.status == "success"
        ]
        if not successful or self.session is None:
            return None

        safety_text = json.dumps(
            {
                "request": message,
                "agent_results": [
                    {
                        "agent": result.agent,
                        "data": result.data,
                    }
                    for result in successful
                ],
            },
            ensure_ascii=False,
            default=str,
        )[:12000]
        try:
            assessment = await asyncio.wait_for(
                SafetyAgentService(self.session).assess(safety_text),
                timeout=SAFETY_TIMEOUT_SECONDS,
            )
            return AgentResult(
                agent="safety",
                status="success",
                data=assessment.model_dump(mode="json"),
            )
        except TimeoutError:
            logger.warning("Safety Agent timed out")
            return AgentResult(
                agent="safety",
                status="error",
                data={
                    "status": "warning",
                    "risk_level": "medium",
                    "error": "Safety Agent timed out; human review is required.",
                },
            )
        except Exception as exc:
            logger.warning("Safety Agent error: %s", exc)
            return AgentResult(
                agent="safety",
                status="error",
                data={
                    "status": "warning",
                    "risk_level": "medium",
                    "error": "Safety Agent unavailable; human review is required.",
                },
            )

    async def _handle_content(
        self, ctx: OrchestratorContext, normalised: str
    ) -> tuple[list[AgentResult], list[str]]:
        if self.session is None:
            return [AgentResult(agent="content", status="error", data={"error": "Session required"})], ["content"]
        
        req = ContentGenerateRequest(
            content_type=ctx.content_type or "promotion",
            topic=ctx.topic or normalised,
            audience=ctx.audience or "sportifs au Maroc",
            tone=ctx.tone or "premium",
            language=ctx.language or "fr",
            product_id=ctx.product_id,
        )

        try:
            service = ContentAgentService(self.session)
            result = await service.preview(req)
            return [AgentResult(agent="content", status="success", data=result.model_dump(mode="json"))], ["content"]
        except HTTPException as exc:
            return [AgentResult(agent="content", status="error", data={"error": exc.detail, "status_code": exc.status_code})], ["content"]
        except Exception as exc:
            logger.warning("ContentAgent preview error: %s", exc)
            return [AgentResult(agent="content", status="error", data={"error": str(exc)})], ["content"]

    async def _handle_marketing(
        self, ctx: OrchestratorContext, normalised: str
    ) -> tuple[list[AgentResult], list[str]]:
        if self.session is None:
            return [AgentResult(agent="marketing", status="error", data={"error": "Session required"})], ["marketing"]
        
        req = MarketingGenerateRequest(
            campaign_type=ctx.campaign_type or "promotion",
            topic=ctx.topic or normalised,
            objective=ctx.objective or "Engagement communautaire",
            audience=ctx.audience or "sportifs au Maroc",
            tone=ctx.tone or "premium",
            channels=ctx.channels or ["email"],
            product_id=ctx.product_id,
            offer_details=ctx.offer_details,
        )

        try:
            service = MarketingAgentService(self.session)
            result = await service.preview(req)
            return [AgentResult(agent="marketing", status="success", data=result.model_dump(mode="json"))], ["marketing"]
        except HTTPException as exc:
            return [AgentResult(agent="marketing", status="error", data={"error": exc.detail, "status_code": exc.status_code})], ["marketing"]
        except Exception as exc:
            logger.warning("MarketingAgent preview error: %s", exc)
            return [AgentResult(agent="marketing", status="error", data={"error": str(exc)})], ["marketing"]

    async def _handle_analytics(
        self,
        ctx: OrchestratorContext,
    ) -> tuple[list[AgentResult], list[str]]:
        if self.session is None:
            return [
                AgentResult(
                    agent="analytics",
                    status="error",
                    data={"error": "Session required"},
                )
            ], ["analytics"]
        try:
            report = await AnalyticsAgentService(self.session).report(
                ctx.period_days or 30,
                use_ai=False,
            )
            return [
                AgentResult(
                    agent="analytics",
                    status="success",
                    data=report.model_dump(mode="json"),
                )
            ], ["analytics"]
        except Exception as exc:
            logger.warning("AnalyticsAgent report error: %s", exc)
            return [
                AgentResult(
                    agent="analytics",
                    status="error",
                    data={"error": str(exc)},
                )
            ], ["analytics"]

    async def _handle_stock_forecast(
        self,
        ctx: OrchestratorContext,
    ) -> tuple[list[AgentResult], list[str]]:
        if self.session is None:
            return [
                AgentResult(
                    agent="stock_forecast",
                    status="error",
                    data={"error": "Session required"},
                )
            ], ["stock_forecast"]
        try:
            report = await StockForecastAgentService(self.session).report(
                ctx.lookback_days or 30,
                target_cover_days=30,
                use_ai=False,
            )
            return [
                AgentResult(
                    agent="stock_forecast",
                    status="success",
                    data=report.model_dump(mode="json"),
                )
            ], ["stock_forecast"]
        except Exception as exc:
            logger.warning("StockForecastAgent report error: %s", exc)
            return [
                AgentResult(
                    agent="stock_forecast",
                    status="error",
                    data={"error": str(exc)},
                )
            ], ["stock_forecast"]
