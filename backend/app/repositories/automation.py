from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation import AutomationOutbox
from app.models.cart import CartItem
from app.models.operations import AuditLog
from app.models.user import User


class AutomationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def abandoned_carts(
        self,
        *,
        older_than: datetime,
    ) -> list[tuple[int, str, datetime, int]]:
        result = await self.session.execute(
            select(
                User.id,
                User.email,
                func.max(CartItem.updated_at),
                func.sum(CartItem.quantity),
            )
            .join(CartItem, CartItem.user_id == User.id)
            .where(
                CartItem.updated_at <= older_than,
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
            .group_by(User.id, User.email)
        )
        return [
            (int(row[0]), str(row[1]), row[2], int(row[3]))
            for row in result.all()
        ]

    async def event_logged_recently(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: str | int,
        days: int,
    ) -> bool:
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self.session.execute(
            select(AuditLog.id)
            .where(
                AuditLog.action == action,
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == str(entity_id),
                AuditLog.created_at >= since,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    def add_outbox(
        self,
        *,
        event_type: str,
        channel: str,
        recipient: str,
        body: str,
        subject: str | None = None,
        reference_type: str | None = None,
        reference_id: str | int | None = None,
    ) -> AutomationOutbox:
        item = AutomationOutbox(
            event_type=event_type,
            channel=channel,
            recipient=recipient,
            subject=subject,
            body=body,
            reference_type=reference_type,
            reference_id=(
                str(reference_id) if reference_id is not None else None
            ),
        )
        self.session.add(item)
        return item

    async def pending_outbox(self, limit: int) -> list[AutomationOutbox]:
        result = await self.session.execute(
            select(AutomationOutbox)
            .where(AutomationOutbox.status == "pending")
            .order_by(AutomationOutbox.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def complete_outbox(
        self,
        item_id: int,
        *,
        success: bool,
        error: str | None,
    ) -> AutomationOutbox | None:
        item = await self.session.get(AutomationOutbox, item_id)
        if item is None:
            return None
        item.attempts += 1
        item.status = "sent" if success else "failed"
        item.last_error = None if success else error
        item.processed_at = datetime.now(UTC)
        await self.session.commit()
        return item

