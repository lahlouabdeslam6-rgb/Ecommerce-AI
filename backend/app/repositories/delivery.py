from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import AuditLog
from app.models.order import Order
from app.models.user import User


class DeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active_orders(self) -> list[tuple[Order, str]]:
        result = await self.session.execute(
            select(Order, Order.email)
            .outerjoin(User, User.id == Order.user_id)
            .where(
                Order.order_status.not_in({"delivered", "cancelled"}),
                (User.id.is_(None)) | (User.is_deleted.is_(False)),
            )
            .order_by(Order.created_at)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def alert_sent_since(
        self,
        order_id: int,
        since: datetime,
    ) -> bool:
        result = await self.session.execute(
            select(AuditLog.id)
            .where(
                AuditLog.action == "delivery.alert_sent",
                AuditLog.entity_type == "order",
                AuditLog.entity_id == str(order_id),
                AuditLog.created_at >= since,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
