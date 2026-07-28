from collections import Counter
from datetime import UTC, datetime, timedelta
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.repositories.order_verification import OrderVerificationRepository
from app.schemas.order_verification import (
    OrderVerificationItem,
    OrderVerificationReport,
    OrderVerificationSummary,
    VerificationStatus,
)


class OrderVerificationAgentService:
    """Read-only COD verification assistant. A human keeps every final decision."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        repository: OrderVerificationRepository | None = None,
    ) -> None:
        self.repository = repository or OrderVerificationRepository(session)

    async def report(self) -> OrderVerificationReport:
        generated_at = datetime.now(UTC)
        orders = await self.repository.recent_orders(
            generated_at - timedelta(days=90)
        )
        candidates = [
            order for order in orders if order.order_status == "pending"
        ]
        items = [
            self._assess(order, orders, generated_at)
            for order in candidates
        ]
        items.sort(key=lambda item: (-item.priority_score, item.created_at))
        counts = Counter(item.verification_status for item in items)
        summary = OrderVerificationSummary(
            orders_to_review=len(items),
            to_confirm=counts["to_confirm"],
            priority_review=counts["priority_review"],
            possible_duplicate=counts["possible_duplicate"],
            ready_to_prepare=counts["ready_to_prepare"],
        )
        analysis = (
            "Aucune commande en attente de vérification."
            if not items
            else (
                f"{len(items)} commande(s) à vérifier : "
                f"{summary.priority_review} prioritaire(s), "
                f"{summary.possible_duplicate} doublon(s) possible(s) et "
                f"{summary.ready_to_prepare} prête(s) à préparer."
            )
        )
        return OrderVerificationReport(
            generated_at=generated_at,
            summary=summary,
            items=items,
            analysis=analysis,
        )

    @classmethod
    def _assess(
        cls,
        order: Order,
        history: list[Order],
        generated_at: datetime,
    ) -> OrderVerificationItem:
        phone = cls._phone(order.phone)
        email = order.email.strip().lower()
        address = cls._text(order.address)
        recent_limit = generated_at - timedelta(days=7)
        peers = [item for item in history if item.id != order.id]

        duplicate_orders = [
            item
            for item in peers
            if cls._as_utc(item.created_at) >= recent_limit
            and item.order_status in {"pending", "confirmed", "preparing"}
            and (
                (phone and cls._phone(item.phone) == phone)
                or (
                    item.email.strip().lower() == email
                    and cls._text(item.address) == address
                )
            )
        ]
        failed_history = [
            item
            for item in peers
            if item.order_status in {"cancelled", "delivery_failed"}
            and (
                (phone and cls._phone(item.phone) == phone)
                or item.email.strip().lower() == email
            )
        ]
        delivered_history = [
            item
            for item in peers
            if item.order_status == "delivered"
            and (
                (phone and cls._phone(item.phone) == phone)
                or item.email.strip().lower() == email
            )
        ]

        signals: list[str] = []
        score = 10
        incomplete = False
        if len(phone) < 9:
            signals.append("Numéro de téléphone à vérifier")
            score += 40
            incomplete = True
        if len(address) < 8 or len(order.city.strip()) < 2:
            signals.append("Adresse de livraison incomplète")
            score += 40
            incomplete = True
        if duplicate_orders:
            signals.append(
                f"{len(duplicate_orders)} commande(s) active(s) similaire(s)"
            )
            score += 70
        if len(failed_history) >= 2:
            signals.append(
                f"{len(failed_history)} ancien(s) échec(s) ou annulation(s)"
            )
            score += 45
        elif failed_history:
            signals.append("Un ancien échec ou une annulation")
            score += 15
        if order.total >= 1500:
            signals.append("Montant élevé à confirmer")
            score += 25
        if order.user_id is None:
            signals.append("Commande passée sans compte")
            score += 10
        if delivered_history:
            signals.append("Client avec livraison réussie")
            score = max(0, score - 20)

        status: VerificationStatus
        action: str
        if duplicate_orders:
            status = "possible_duplicate"
            action = "Appeler le client avant toute préparation et vérifier le doublon."
        elif incomplete or len(failed_history) >= 2 or order.total >= 1500:
            status = "priority_review"
            action = "Vérification téléphonique prioritaire par le support."
        elif delivered_history and not failed_history:
            status = "ready_to_prepare"
            action = "Coordonnées cohérentes. Confirmer humainement puis préparer."
        else:
            status = "to_confirm"
            action = "Appeler le client pour confirmer la commande et l'adresse."

        return OrderVerificationItem(
            order_id=order.id,
            user_id=order.user_id,
            customer_name=order.full_name,
            customer_email=order.email,
            phone=order.phone,
            address=order.address,
            city=order.city,
            total=order.total,
            currency=order.currency,
            payment_method=order.payment_method,
            created_at=order.created_at,
            verification_status=status,
            priority_score=min(score, 100),
            signals=signals or ["Aucun signal particulier"],
            recommended_action=action,
        )

    @staticmethod
    def _phone(value: str) -> str:
        return re.sub(r"\D", "", value or "")

    @staticmethod
    def _text(value: str) -> str:
        return " ".join((value or "").strip().lower().split())

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
