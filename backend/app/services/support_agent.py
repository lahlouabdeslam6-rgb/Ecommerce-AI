from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.ai_infrastructure import get_ai_http_client
from app.models.order import Order
from app.models.user import User
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.schemas.support_agent import (
    SupportAgentRequest,
    SupportAgentResponse,
    SupportOrderContext,
    SupportProductContext,
)
from app.services.safety_agent import SafetyAgentService
from app.services.support import SupportService


logger = logging.getLogger("nutrifit.support_agent")

OLLAMA_SUPPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "needs_human": {"type": "boolean"},
        "suggested_questions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["answer", "needs_human", "suggested_questions"],
    "additionalProperties": False,
}

ORDER_STATUS_LABELS = {
    "pending": "En attente",
    "confirmed": "Confirmée",
    "preparing": "En préparation",
    "shipped": "Expédiée",
    "delivered": "Livrée",
    "delivery_failed": "Échec de livraison",
    "cancelled": "Annulée",
}

STOP_WORDS = {
    "avec", "dans", "pour", "quel", "quelle", "quels", "quelles", "produit",
    "bonjour", "merci", "comment", "est", "une", "des", "les", "mon", "ma",
    "mes", "sur", "son", "ses", "votre", "vous", "peux", "puis", "avoir",
}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", without_accents).strip().lower()


class SupportAgentService:
    def __init__(
        self,
        session: AsyncSession,
        user: User,
        *,
        order_repository: OrderRepository | None = None,
        product_repository: ProductRepository | None = None,
        support_service: SupportService | None = None,
    ) -> None:
        self.session = session
        self.user = user
        self.order_repository = order_repository or OrderRepository(session)
        self.product_repository = product_repository or ProductRepository()
        self.support_service = support_service or SupportService(session)

    async def preview(
        self,
        request: SupportAgentRequest,
        *,
        use_ai: bool = True,
    ) -> SupportAgentResponse:
        normalized = _normalize(request.message)
        topic = self._detect_topic(normalized)

        if topic == "greeting":
            return SupportAgentResponse(
                topic=topic,
                answer=(
                    "Bonjour et bienvenue chez NUTRIFIT ! Comment puis-je vous "
                    "aider aujourd'hui ? Je peux vous conseiller sur les produits, "
                    "le paiement, la livraison ou le suivi de votre commande."
                ),
                needs_human=False,
                suggested_questions=[
                    "Je cherche un produit",
                    "Où est ma dernière commande ?",
                    "Comment fonctionne la livraison ?",
                ],
                model="accueil NUTRIFIT",
            )

        if topic == "medical_safety":
            return SupportAgentResponse(
                topic=topic,
                answer=(
                    "Je ne peux pas établir de diagnostic ni confirmer qu'un "
                    "complément convient à une maladie, une grossesse ou un "
                    "traitement. Demandez conseil à un médecin ou à un pharmacien "
                    "avant toute utilisation."
                ),
                needs_human=False,
                safety_notice=(
                    "Les informations de l'assistant ne remplacent pas l'avis "
                    "d'un professionnel de santé."
                ),
                suggested_questions=[
                    "Voir les informations d'un produit",
                    "Contacter le support pour une commande",
                ],
                model="règles de sécurité",
            )

        order = await self._resolve_order(request, normalized, topic)
        if topic == "order" and order is not None:
            context = self._order_context(order)
            if self._is_delay_escalation(normalized):
                ticket, created = await self.support_service.handoff_delayed_order(
                    self.user,
                    order_id=order.id,
                    message=request.message,
                )
                handoff_message = (
                    "Votre signalement a été transmis au support humain. "
                    "Notre équipe va examiner le retard et vous répondre dans "
                    "les plus brefs délais."
                    if created
                    else (
                        "Cette commande possède déjà une demande ouverte auprès "
                        "du support humain. Notre équipe va la prendre en charge "
                        "dans les plus brefs délais."
                    )
                )
                return SupportAgentResponse(
                    topic=topic,
                    answer=(
                        f"La commande #{order.id} est actuellement "
                        f"« {context.order_status_label} »."
                    ),
                    needs_human=True,
                    order=context,
                    suggested_questions=["Suivre ma demande de support"],
                    support_url=f"/help?ticket={ticket.id}",
                    ticket_id=ticket.id,
                    ticket_created=created,
                    handoff_message=handoff_message,
                    model="données de commande + support humain",
                    read_only=False,
                )
            return SupportAgentResponse(
                topic=topic,
                answer=(
                    f"La commande #{order.id} est actuellement "
                    f"« {context.order_status_label} ». Son paiement est "
                    f"« {self._payment_status_label(order.payment_status)} »."
                ),
                needs_human=order.order_status == "delivery_failed",
                order=context,
                suggested_questions=[
                    "Comment fonctionne la livraison ?",
                    "Comment contacter le support humain ?",
                ],
                model="données de commande",
            )

        if topic == "order" and order is None:
            return SupportAgentResponse(
                topic=topic,
                answer=(
                    "Je n'ai trouvé aucune commande correspondant à votre compte. "
                    "Vérifiez le numéro ou contactez le support humain."
                ),
                needs_human=True,
                suggested_questions=["Afficher mes commandes"],
                model="données de commande",
            )

        if topic == "payment":
            return SupportAgentResponse(
                topic=topic,
                answer=(
                    "NUTRIFIT propose le paiement à la livraison. Le paiement par "
                    "carte présent sur cette version locale fonctionne uniquement "
                    "en mode test et aucun débit bancaire réel n'est effectué."
                ),
                needs_human=False,
                suggested_questions=[
                    "Où est ma dernière commande ?",
                    "Comment fonctionne la livraison ?",
                ],
                model="règles du site",
            )

        if topic == "delivery":
            return SupportAgentResponse(
                topic=topic,
                answer=(
                    "La livraison est proposée partout au Maroc. Pour connaître "
                    "l'état exact d'un colis, indiquez le numéro de commande ou "
                    "demandez le statut de votre dernière commande."
                ),
                needs_human=False,
                order=self._order_context(order) if order else None,
                suggested_questions=[
                    "Où est ma dernière commande ?",
                    "J'ai un problème de livraison",
                ],
                model="règles du site",
            )

        if topic == "return":
            return SupportAgentResponse(
                topic=topic,
                answer=(
                    "Une demande de retour doit être vérifiée par l'équipe support "
                    "selon la commande et l'état du produit. Ouvrez une demande en "
                    "indiquant le numéro de commande et la raison du retour."
                ),
                needs_human=True,
                suggested_questions=["Ouvrir une demande de retour"],
                model="règles du site",
            )

        product = await self._resolve_product(request, normalized)
        if topic == "product" and product is not None:
            product_context = self._product_context(product)
            if use_ai:
                generated = await self._generate_answer(
                    request.message,
                    topic,
                    product=product_context,
                    order=None,
                )
                if generated is not None:
                    return await self._safe_response(
                        topic=topic,
                        generated=generated,
                        product=product_context,
                    )
            ingredient_text = (
                ", ".join(product_context.ingredients[:8])
                if product_context.ingredients
                else "non renseignés dans le catalogue"
            )
            return SupportAgentResponse(
                topic=topic,
                answer=(
                    f"{product_context.name} est classé dans "
                    f"{product_context.category or 'la nutrition sportive'}. "
                    f"Les ingrédients enregistrés sont : {ingredient_text}. "
                    "Consultez la fiche produit pour les informations complètes."
                ),
                needs_human=False,
                product=product_context,
                suggested_questions=[
                    "Ce produit est-il en stock ?",
                    "Voir la fiche produit",
                ],
                model="catalogue",
            )

        if use_ai:
            generated = await self._generate_answer(
                request.message,
                topic,
                product=None,
                order=self._order_context(order) if order else None,
            )
            if generated is not None:
                return await self._safe_response(
                    topic=topic,
                    generated=generated,
                    order=self._order_context(order) if order else None,
                )

        return SupportAgentResponse(
            topic="general",
            answer=(
                "Je ne dispose pas d'une information suffisamment fiable pour "
                "répondre à cette demande. Vous pouvez transmettre votre question "
                "à l'équipe support."
            ),
            needs_human=True,
            suggested_questions=[
                "Où est ma dernière commande ?",
                "Comment fonctionne le paiement à la livraison ?",
            ],
            model="réponse de secours",
        )

    async def _resolve_order(
        self,
        request: SupportAgentRequest,
        normalized: str,
        topic: str,
    ) -> Order | None:
        order_id = request.order_id
        if order_id is None:
            match = re.search(r"\bcommande\s*#?\s*(\d+)\b", normalized)
            if match:
                order_id = int(match.group(1))
        if order_id is not None:
            return await self.order_repository.get_by_id(
                order_id,
                user_id=self.user.id,
            )
        if topic not in {"order", "delivery"}:
            return None
        orders, _ = await self.order_repository.list_orders(
            page=1,
            page_size=1,
            user_id=self.user.id,
        )
        return orders[0] if orders else None

    async def _resolve_product(
        self,
        request: SupportAgentRequest,
        normalized: str,
    ) -> dict[str, Any] | None:
        if request.product_id is not None:
            product = await self.product_repository.get_by_product_id(
                request.product_id
            )
            return product if product and product.get("is_active", True) else None

        products, _ = await self.product_repository.list_products(
            skip=0,
            limit=500,
            active_only=True,
            sort_by="newest",
        )
        message_tokens = set(re.findall(r"[a-z0-9]+", normalized)) - STOP_WORDS
        best: dict[str, Any] | None = None
        best_score = 0
        for product in products:
            searchable = _normalize(
                " ".join(
                    str(product.get(field) or "")
                    for field in ("name", "brand", "category")
                )
            )
            product_tokens = set(re.findall(r"[a-z0-9]+", searchable)) - STOP_WORDS
            score = len(message_tokens & product_tokens)
            if score > best_score:
                best = product
                best_score = score
        return best if best_score > 0 else None

    async def _safe_response(
        self,
        *,
        topic: str,
        generated: dict[str, Any],
        product: SupportProductContext | None = None,
        order: SupportOrderContext | None = None,
    ) -> SupportAgentResponse:
        answer = str(generated.get("answer") or "").strip()[:3000]
        if not answer:
            answer = "Le Support Agent n'a pas pu préparer une réponse fiable."
        assessment = await SafetyAgentService(self.session).assess(
            answer,
            use_ai=False,
        )
        if assessment.status == "blocked":
            return SupportAgentResponse(
                topic=topic,
                answer=(
                    "Cette question nécessite une réponse prudente. Consultez un "
                    "médecin ou un pharmacien pour tout sujet de santé, ou contactez "
                    "le support humain pour une question de commande."
                ),
                needs_human=True,
                product=product,
                order=order,
                safety_notice="La réponse générée a été bloquée par Safety Agent.",
                suggested_questions=["Contacter le support humain"],
                model="Safety Agent",
            )
        return SupportAgentResponse(
            topic=topic,
            answer=answer,
            needs_human=bool(generated.get("needs_human")),
            product=product,
            order=order,
            safety_notice=(
                "Cette réponse contient un point à vérifier avec un professionnel."
                if assessment.status == "warning"
                else None
            ),
            suggested_questions=self._clean_questions(
                generated.get("suggested_questions")
            ),
            model=settings.ollama_chat_model,
        )

    async def _generate_answer(
        self,
        message: str,
        topic: str,
        *,
        product: SupportProductContext | None,
        order: SupportOrderContext | None,
    ) -> dict[str, Any] | None:
        context = {
            "topic": topic,
            "message": message,
            "product": product.model_dump(mode="json") if product else None,
            "order": order.model_dump(mode="json") if order else None,
            "site_rules": {
                "delivery": "Livraison partout au Maroc.",
                "cod": "Paiement à la livraison disponible.",
                "card": "Paiement par carte en mode test local, sans débit réel.",
                "returns": "Toute demande de retour doit être vérifiée par le support humain.",
            },
        }
        prompt = (
            "Tu es Support Agent de NUTRIFIT. Réponds en français avec un ton "
            "clair et professionnel. Utilise uniquement les données fournies. "
            "N'invente jamais un délai, un stock, un ingrédient, une politique de "
            "retour ou un statut de commande. Ne donne aucun diagnostic ni dosage "
            "médical. Si les données sont insuffisantes, indique needs_human=true. "
            "Retourne uniquement un JSON avec answer, needs_human et "
            "suggested_questions.\n"
            f"{json.dumps(context, ensure_ascii=False)}"
        )
        try:
            response = await get_ai_http_client().post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_chat_model,
                    "prompt": prompt,
                    "format": OLLAMA_SUPPORT_SCHEMA,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 700},
                },
                timeout=60,
            )
            response.raise_for_status()
            data = json.loads(str(response.json().get("response") or ""))
            return data if isinstance(data, dict) else None
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Support Agent generation unavailable: %s", exc)
            return None

    @staticmethod
    def _detect_topic(normalized: str) -> str:
        tokens = set(re.findall(r"[a-z0-9]+", normalized))
        greeting_words = {
            "bonjour", "bonsoir", "hello", "hey", "hi", "salam", "salut", "slm",
        }
        greeting_fillers = {
            "ca", "cava", "cv", "kidayr", "kidayra", "labas", "va",
        }
        if tokens & greeting_words and tokens <= (greeting_words | greeting_fillers):
            return "greeting"
        if tokens & {
            "grossesse", "enceinte", "allaitement", "maladie", "medicament",
            "traitement", "diabete", "cancer", "hypertension", "diagnostic",
        }:
            return "medical_safety"
        if tokens & {"retour", "remboursement", "rembourser", "echanger"}:
            return "return"
        if tokens & {"paiement", "payer", "carte", "cod", "cash"}:
            return "payment"
        if tokens & {
            "commande", "commende", "comande", "colis", "statut", "suivi",
            "tracking", "retard", "retardee", "t3atlat", "ta3tlat",
            "m3etla",
        }:
            return "order"
        if tokens & {"livraison", "livrer", "transport"}:
            return "delivery"
        if tokens & {
            "produit", "ingredient", "ingredients", "stock", "proteine",
            "creatine", "whey", "vitamine", "omega",
        }:
            return "product"
        return "general"

    @staticmethod
    def _is_delay_escalation(normalized: str) -> bool:
        tokens = set(re.findall(r"[a-z0-9]+", normalized))
        return bool(
            tokens
            & {
                "retard",
                "retardee",
                "bloquee",
                "t3atlat",
                "ta3tlat",
                "m3etla",
                "mawsletch",
                "mabghatch",
            }
        )

    @staticmethod
    def _order_context(order: Order) -> SupportOrderContext:
        return SupportOrderContext(
            order_id=order.id,
            order_status=order.order_status,
            order_status_label=ORDER_STATUS_LABELS.get(
                order.order_status,
                order.order_status,
            ),
            payment_method=order.payment_method,
            payment_status=order.payment_status,
            total=order.total,
            currency=order.currency,
        )

    @staticmethod
    def _product_context(product: dict[str, Any]) -> SupportProductContext:
        ingredients = []
        for ingredient in product.get("ingredients") or []:
            value = (
                ingredient.get("name")
                if isinstance(ingredient, dict)
                else str(ingredient)
            )
            if value:
                ingredients.append(str(value))
        return SupportProductContext(
            product_id=int(product["product_id"]),
            name=str(product.get("name") or "Produit"),
            brand=product.get("brand"),
            category=product.get("category"),
            price=(
                float(product["price"])
                if product.get("price") is not None
                else None
            ),
            currency=str(product.get("currency") or "MAD"),
            stock=max(int(product.get("stock") or 0), 0),
            ingredients=ingredients[:20],
        )

    @staticmethod
    def _payment_status_label(status: str) -> str:
        return {
            "paid": "Payé",
            "pending": "En attente",
            "cancelled": "Annulé",
        }.get(status, status)

    @staticmethod
    def _clean_questions(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [
            str(item).strip()[:180]
            for item in value
            if str(item).strip()
        ][:4]
