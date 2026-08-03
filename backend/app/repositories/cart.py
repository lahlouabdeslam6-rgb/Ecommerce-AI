from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import CartItem, PackCartItem


class CartRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_items(self, user_id: int) -> list[CartItem]:
        result = await self.session.execute(
            select(CartItem)
            .where(CartItem.user_id == user_id)
            .order_by(CartItem.created_at)
        )
        return list(result.scalars().all())

    async def get_item(self, user_id: int, product_id: int) -> CartItem | None:
        result = await self.session.execute(
            select(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.product_id == product_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_pack_items(self, user_id: int) -> list[PackCartItem]:
        result = await self.session.execute(
            select(PackCartItem)
            .where(PackCartItem.user_id == user_id)
            .order_by(PackCartItem.created_at)
        )
        return list(result.scalars().all())

    async def get_pack_item(self, user_id: int, pack_id: int) -> PackCartItem | None:
        result = await self.session.execute(
            select(PackCartItem).where(
                PackCartItem.user_id == user_id,
                PackCartItem.pack_id == pack_id,
            )
        )
        return result.scalar_one_or_none()

    async def set_quantity(
        self,
        *,
        user_id: int,
        product_id: int,
        quantity: int,
    ) -> CartItem:
        item = await self.get_item(user_id, product_id)
        if item is None:
            item = CartItem(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
            )
            self.session.add(item)
        else:
            item.quantity = quantity
            item.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def remove_item(self, user_id: int, product_id: int) -> bool:
        result = await self.session.execute(
            delete(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.product_id == product_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def set_pack_quantity(self, *, user_id: int, pack_id: int, quantity: int) -> PackCartItem:
        item = await self.get_pack_item(user_id, pack_id)
        if item is None:
            item = PackCartItem(user_id=user_id, pack_id=pack_id, quantity=quantity)
            self.session.add(item)
        else:
            item.quantity = quantity
            item.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def remove_pack_item(self, user_id: int, pack_id: int) -> bool:
        result = await self.session.execute(
            delete(PackCartItem).where(
                PackCartItem.user_id == user_id,
                PackCartItem.pack_id == pack_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def clear(self, user_id: int, *, commit: bool = True) -> None:
        await self.session.execute(delete(CartItem).where(CartItem.user_id == user_id))
        await self.session.execute(delete(PackCartItem).where(PackCartItem.user_id == user_id))
        if commit:
            await self.session.commit()
