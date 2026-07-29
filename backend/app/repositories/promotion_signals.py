from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promotion_signal import ProductCost, ProductView


class PromotionSignalsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_cost(self, product_id: int) -> ProductCost | None:
        return await self.session.get(ProductCost, product_id)

    async def upsert_cost(
        self,
        *,
        product_id: int,
        cost_price: float,
        currency: str,
        updated_by: int,
    ) -> ProductCost:
        cost = await self.get_cost(product_id)
        if cost is None:
            cost = ProductCost(
                product_id=product_id,
                cost_price=cost_price,
                currency=currency,
                updated_by=updated_by,
            )
            self.session.add(cost)
        else:
            cost.cost_price = cost_price
            cost.currency = currency
            cost.updated_by = updated_by
            cost.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(cost)
        return cost

    async def cost_map(self, product_ids: list[int]) -> dict[int, float]:
        if not product_ids:
            return {}
        rows = (
            await self.session.execute(
                select(ProductCost.product_id, ProductCost.cost_price).where(
                    ProductCost.product_id.in_(product_ids)
                )
            )
        ).all()
        return {
            int(row.product_id): float(row.cost_price)
            for row in rows
        }

    def add_view(self, product_id: int) -> None:
        self.session.add(ProductView(product_id=product_id))

    async def view_counts(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> dict[int, int]:
        rows = (
            await self.session.execute(
                select(
                    ProductView.product_id,
                    func.count(ProductView.id).label("views"),
                )
                .where(
                    ProductView.viewed_at >= start,
                    ProductView.viewed_at < end,
                )
                .group_by(ProductView.product_id)
            )
        ).all()
        return {
            int(row.product_id): int(row.views)
            for row in rows
        }
