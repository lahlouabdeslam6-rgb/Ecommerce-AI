from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order


class OrderVerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recent_orders(self, since: datetime) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .where(Order.created_at >= since)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
