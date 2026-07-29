from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.order import Order, OrderItem


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def metrics(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[str, int | float]:
        period = (Order.created_at >= start, Order.created_at < end)
        orders = int(
            (
                await self.session.execute(
                    select(func.count(Order.id)).where(*period)
                )
            ).scalar_one()
        )
        paid_orders, revenue = (
            await self.session.execute(
                select(
                    func.count(Order.id),
                    func.coalesce(func.sum(Order.total), 0),
                ).where(*period, Order.payment_status == "paid")
            )
        ).one()
        delivered = int(
            (
                await self.session.execute(
                    select(func.count(Order.id)).where(
                        *period,
                        Order.order_status == "delivered",
                    )
                )
            ).scalar_one()
        )
        cancelled = int(
            (
                await self.session.execute(
                    select(func.count(Order.id)).where(
                        *period,
                        Order.order_status == "cancelled",
                    )
                )
            ).scalar_one()
        )
        units = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(OrderItem.quantity), 0))
                    .join(Order, Order.id == OrderItem.order_id)
                    .where(*period, Order.order_status != "cancelled")
                )
            ).scalar_one()
        )
        paid_count = int(paid_orders)
        revenue_value = round(float(revenue), 2)
        return {
            "orders": orders,
            "paid_orders": paid_count,
            "delivered_orders": delivered,
            "cancelled_orders": cancelled,
            "units_sold": units,
            "revenue_mad": revenue_value,
            "average_order_value_mad": (
                round(revenue_value / paid_count, 2) if paid_count else 0.0
            ),
        }

    async def daily_sales(
        self,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        day = func.date(Order.created_at)
        rows = (
            await self.session.execute(
                select(
                    day.label("day"),
                    func.count(Order.id).label("orders"),
                    func.coalesce(
                        func.sum(
                            case(
                                (Order.payment_status == "paid", Order.total),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("revenue"),
                )
                .where(Order.created_at >= start, Order.created_at < end)
                .group_by(day)
                .order_by(day)
            )
        ).all()
        return [
            {
                "date": row.day,
                "orders": int(row.orders),
                "revenue_mad": round(float(row.revenue), 2),
            }
            for row in rows
        ]

    async def top_products(
        self,
        start: datetime,
        end: datetime,
        *,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(
                    OrderItem.product_id,
                    OrderItem.product_name,
                    OrderItem.brand,
                    func.sum(OrderItem.quantity).label("quantity"),
                    func.sum(OrderItem.subtotal).label("revenue"),
                )
                .join(Order, Order.id == OrderItem.order_id)
                .where(
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.order_status != "cancelled",
                )
                .group_by(
                    OrderItem.product_id,
                    OrderItem.product_name,
                    OrderItem.brand,
                )
                .order_by(
                    func.sum(OrderItem.quantity).desc(),
                    func.sum(OrderItem.subtotal).desc(),
                )
                .limit(limit)
            )
        ).all()
        return [
            {
                "product_id": int(row.product_id),
                "name": str(row.product_name),
                "brand": row.brand,
                "quantity": int(row.quantity),
                "revenue_mad": round(float(row.revenue), 2),
            }
            for row in rows
        ]

    async def sold_product_ids(
        self,
        start: datetime,
        end: datetime,
    ) -> set[int]:
        rows = (
            await self.session.execute(
                select(OrderItem.product_id)
                .join(Order, Order.id == OrderItem.order_id)
                .where(
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.order_status != "cancelled",
                )
                .distinct()
            )
        ).scalars()
        return {int(product_id) for product_id in rows.all()}

    async def co_purchase_pairs(
        self,
        start: datetime,
        end: datetime,
        *,
        limit: int = 500,
    ) -> list[dict[str, int]]:
        left = aliased(OrderItem)
        right = aliased(OrderItem)
        rows = (
            await self.session.execute(
                select(
                    left.product_id.label("left_product_id"),
                    right.product_id.label("right_product_id"),
                    func.count(func.distinct(left.order_id)).label(
                        "order_count"
                    ),
                )
                .join(
                    right,
                    and_(
                        right.order_id == left.order_id,
                        right.product_id > left.product_id,
                    ),
                )
                .join(Order, Order.id == left.order_id)
                .where(
                    Order.created_at >= start,
                    Order.created_at < end,
                    Order.order_status != "cancelled",
                )
                .group_by(left.product_id, right.product_id)
                .order_by(
                    func.count(func.distinct(left.order_id)).desc()
                )
                .limit(limit)
            )
        ).all()
        return [
            {
                "left_product_id": int(row.left_product_id),
                "right_product_id": int(row.right_product_id),
                "order_count": int(row.order_count),
            }
            for row in rows
        ]
