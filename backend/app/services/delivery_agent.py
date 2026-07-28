from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.user import User
from app.repositories.delivery import DeliveryRepository
from app.repositories.automation import AutomationRepository
from app.repositories.operations import OperationsRepository
from app.schemas.delivery import (
    DeliveryOrderItem,
    DeliveryReport,
    DeliverySummary,
)


STATUS_TARGET_HOURS = {
    "pending": 24,
    "confirmed": 48,
    "preparing": 72,
    "shipped": 96,
    "delivery_failed": 0,
}
ESTIMATED_DAYS = {
    "pending": 4,
    "confirmed": 4,
    "preparing": 3,
    "shipped": 2,
}


class DeliveryAgentService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        repository: DeliveryRepository | None = None,
        operations: OperationsRepository | None = None,
        automation: AutomationRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or DeliveryRepository(session)
        self.operations = operations or OperationsRepository(session)
        self.automation = automation or AutomationRepository(session)

    async def report(
        self,
        *,
        notify: bool = False,
        actor: User | None = None,
    ) -> DeliveryReport:
        generated_at = datetime.now(UTC)
        rows = await self.repository.active_orders()
        items = [
            self._assess_order(order, email, generated_at)
            for order, email in rows
        ]
        items.sort(
            key=lambda item: (
                {"failed": 0, "critical": 1, "warning": 2, "normal": 3}[
                    item.risk
                ],
                -item.age_hours,
            )
        )

        alerts_sent = 0
        if notify:
            alerts_sent = await self._notify_priority_orders(
                items,
                generated_at,
                actor,
            )

        summary = DeliverySummary(
            active_orders=len(items),
            normal=sum(item.risk == "normal" for item in items),
            warning=sum(item.risk == "warning" for item in items),
            critical=sum(item.risk == "critical" for item in items),
            failed=sum(item.risk == "failed" for item in items),
            alerts_sent=alerts_sent,
        )
        return DeliveryReport(
            generated_at=generated_at,
            summary=summary,
            items=items,
            analysis=self._analysis(summary),
            read_only=not notify,
        )

    @staticmethod
    def _assess_order(
        order: Order,
        customer_email: str,
        now: datetime,
    ) -> DeliveryOrderItem:
        created_at = order.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age_hours = round(max((now - created_at).total_seconds() / 3600, 0), 1)
        threshold = STATUS_TARGET_HOURS.get(order.order_status, 96)

        if order.order_status == "delivery_failed":
            risk = "failed"
            reason = "La livraison a échoué et nécessite une intervention."
        elif age_hours >= threshold:
            risk = "critical"
            reason = (
                f"La commande est au statut « {order.order_status} » depuis "
                f"{age_hours:.0f} h, au-delà du seuil interne de {threshold} h."
            )
        elif age_hours >= threshold * 0.75:
            risk = "warning"
            reason = (
                f"La commande approche du seuil interne de {threshold} h "
                f"pour le statut « {order.order_status} »."
            )
        else:
            risk = "normal"
            reason = "La commande reste dans la fenêtre de suivi interne."

        estimated_days = ESTIMATED_DAYS.get(order.order_status)
        estimated_date = (
            (now + timedelta(days=estimated_days)).date()
            if estimated_days is not None
            else None
        )
        return DeliveryOrderItem(
            order_id=order.id,
            user_id=order.user_id,
            customer_name=order.full_name,
            customer_email=customer_email,
            phone=order.phone,
            city=order.city,
            order_status=order.order_status,
            created_at=order.created_at,
            age_hours=age_hours,
            estimated_delivery_date=estimated_date,
            risk=risk,
            reason=reason,
            total=order.total,
            currency=order.currency,
        )

    async def _notify_priority_orders(
        self,
        items: list[DeliveryOrderItem],
        now: datetime,
        actor: User | None,
    ) -> int:
        sent = 0
        since = now - timedelta(hours=24)
        for item in items:
            if item.risk not in {"critical", "failed"}:
                continue
            if await self.repository.alert_sent_since(item.order_id, since):
                continue
            title = f"Suivi livraison commande #{item.order_id}"
            if item.user_id is not None:
                self.operations.add_notification(
                    user_id=item.user_id,
                    notification_type="delivery_alert",
                    title=title,
                    message=(
                        "Votre commande nécessite un suivi. "
                        "Notre équipe examine la situation."
                    ),
                    link=f"/orders?order={item.order_id}",
                )
            for role in ("support", "admin"):
                self.operations.add_notification(
                    target_role=role,
                    notification_type="delivery_alert",
                    title=title,
                    message=item.reason,
                    link=(
                        f"/support?order={item.order_id}"
                        if role == "support"
                        else f"/admin?tab=support-delivery&order={item.order_id}"
                    ),
                )
            self.operations.add_audit(
                actor_id=actor.id if actor else None,
                actor_role=actor.role if actor else "automation",
                action="delivery.alert_sent",
                entity_type="order",
                entity_id=item.order_id,
                details={"risk": item.risk, "reason": item.reason},
            )
            external_message = (
                f"Commande NUTRIFIT #{item.order_id}: notre équipe examine "
                "un retard de livraison. Consultez votre compte pour le suivi."
            )
            self.automation.add_outbox(
                event_type="delivery_alert",
                channel="email",
                recipient=item.customer_email,
                subject=f"Suivi de votre commande #{item.order_id}",
                body=external_message,
                reference_type="order",
                reference_id=item.order_id,
            )
            self.automation.add_outbox(
                event_type="delivery_alert",
                channel="whatsapp",
                recipient=item.phone,
                body=external_message,
                reference_type="order",
                reference_id=item.order_id,
            )
            sent += 1
        if sent:
            await self.session.commit()
        return sent

    @staticmethod
    def _analysis(summary: DeliverySummary) -> str:
        priority = summary.critical + summary.failed
        if not summary.active_orders:
            return "Aucune commande active à surveiller."
        if priority:
            return (
                f"{priority} commande(s) nécessitent une intervention rapide "
                f"sur {summary.active_orders} commande(s) active(s)."
            )
        if summary.warning:
            return (
                f"{summary.warning} commande(s) approchent leur seuil de suivi, "
                "sans incident critique détecté."
            )
        return "Toutes les commandes actives restent dans leur fenêtre de suivi."
