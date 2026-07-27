from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: int | None,
        email: str,
        guest_token_hash: str | None = None,
        shipping: dict[str, str | None],
        items: list[dict[str, object]],
        subtotal: float,
        delivery_fee: float,
        payment_method: str,
        payment_status: str,
        card_last4: str | None = None,
        card_brand: str | None = None,
        payment_reference: str | None = None,
    ) -> Order:
        order = Order(
            user_id=user_id,
            email=email.strip().lower(),
            guest_token_hash=guest_token_hash,
            full_name=str(shipping["full_name"]),
            phone=str(shipping["phone"]),
            address=str(shipping["address"]),
            city=str(shipping["city"]),
            notes=shipping.get("notes"),
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total=round(subtotal + delivery_fee, 2),
            currency="MAD",
            payment_method=payment_method,
            payment_status=payment_status,
            card_last4=card_last4,
            card_brand=card_brand,
            payment_reference=payment_reference,
            items=[OrderItem(**item) for item in items],
        )
        self.session.add(order)
        await self.session.flush()
        return order

    async def commit_and_refresh(self, order: Order) -> Order:
        await self.session.commit()
        return await self.get_by_id(order.id, user_id=order.user_id)

    async def get_by_id(
        self,
        order_id: int,
        *,
        user_id: int | None = None,
    ) -> Order | None:
        query = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        if user_id is not None:
            query = query.where(Order.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_orders(
        self,
        *,
        page: int,
        page_size: int,
        user_id: int | None = None,
        order_status: str | None = None,
    ) -> tuple[list[Order], int]:
        conditions = []
        if user_id is not None:
            conditions.append(Order.user_id == user_id)
        if order_status:
            conditions.append(Order.order_status == order_status)

        count_result = await self.session.execute(
            select(func.count(Order.id)).where(*conditions)
        )
        total = int(count_result.scalar_one())
        result = await self.session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(*conditions)
            .order_by(Order.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def recent_product_ids(
        self,
        user_id: int,
        *,
        limit: int = 30,
    ) -> list[int]:
        result = await self.session.execute(
            select(OrderItem.product_id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.user_id == user_id,
                Order.order_status != "cancelled",
            )
            .order_by(Order.created_at.desc(), OrderItem.id.desc())
            .limit(limit)
        )
        product_ids: list[int] = []
        for product_id in result.scalars().all():
            value = int(product_id)
            if value not in product_ids:
                product_ids.append(value)
        return product_ids

    async def dashboard_counts(self) -> dict[str, int | float]:
        total = int(
            (await self.session.execute(select(func.count(Order.id)))).scalar_one()
        )
        pending = int(
            (
                await self.session.execute(
                    select(func.count(Order.id)).where(
                        Order.order_status == "pending"
                    )
                )
            ).scalar_one()
        )
        delivered = int(
            (
                await self.session.execute(
                    select(func.count(Order.id)).where(
                        Order.order_status == "delivered"
                    )
                )
            ).scalar_one()
        )
        revenue = float(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(Order.total), 0)).where(
                        Order.payment_status == "paid"
                    )
                )
            ).scalar_one()
        )
        return {
            "orders": total,
            "pending_orders": pending,
            "delivered_orders": delivered,
            "revenue_mad": round(revenue, 2),
        }

    async def update_status(self, order: Order, new_status: str) -> Order:
        order.order_status = new_status
        if new_status == "delivered":
            order.payment_status = "paid"
        elif new_status == "cancelled":
            order.payment_status = "cancelled"
        elif order.payment_method != "card":
            order.payment_status = "pending"
        order.updated_at = datetime.now(UTC)
        await self.session.commit()
        refreshed = await self.get_by_id(order.id)
        if refreshed is None:
            raise RuntimeError("Order disappeared after update")
        return refreshed
