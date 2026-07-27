from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem


class StockForecastRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def product_sales(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[int, int]:
        rows = (
            await self.session.execute(
                select(
                    OrderItem.product_id,
                    func.sum(OrderItem.quantity).label("quantity"),
                )
                .join(Order, Order.id == OrderItem.order_id)
                .where(
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.order_status != "cancelled",
                )
                .group_by(OrderItem.product_id)
            )
        ).all()
        return {
            int(row.product_id): int(row.quantity)
            for row in rows
        }
