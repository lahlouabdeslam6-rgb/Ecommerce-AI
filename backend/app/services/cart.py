from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.cart import CartRepository
from app.repositories.product import ProductRepository
from app.schemas.cart import CartItemResponse, CartResponse


class CartService:
    def __init__(self, session: AsyncSession) -> None:
        self.cart_repository = CartRepository(session)
        self.product_repository = ProductRepository()

    async def get_cart(self, user_id: int) -> CartResponse:
        cart_items = await self.cart_repository.list_items(user_id)
        products = await self.product_repository.get_many_by_ids(
            [item.product_id for item in cart_items]
        )
        response_items: list[CartItemResponse] = []
        subtotal = 0.0

        for item in cart_items:
            product = products.get(item.product_id)
            if product is None:
                response_items.append(
                    CartItemResponse(
                        product_id=item.product_id,
                        name="Unavailable product",
                        unit_price=0,
                        currency="MAD",
                        quantity=item.quantity,
                        subtotal=0,
                        stock=0,
                        is_available=False,
                    )
                )
                continue

            unit_price = float(product.get("price") or 0)
            line_subtotal = round(unit_price * item.quantity, 2)
            available = bool(product.get("is_active")) and int(
                product.get("stock") or 0
            ) >= item.quantity
            images = product.get("images") or []
            response_items.append(
                CartItemResponse(
                    product_id=item.product_id,
                    name=product.get("name") or "Unnamed product",
                    brand=product.get("brand"),
                    image_url=images[0] if images else None,
                    unit_price=unit_price,
                    currency=product.get("currency") or "MAD",
                    quantity=item.quantity,
                    subtotal=line_subtotal,
                    stock=int(product.get("stock") or 0),
                    is_available=available,
                )
            )
            subtotal += line_subtotal

        return CartResponse(
            items=response_items,
            item_count=sum(item.quantity for item in cart_items),
            subtotal=round(subtotal, 2),
        )

    async def add_item(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
    ) -> CartResponse:
        existing = await self.cart_repository.get_item(user_id, product_id)
        new_quantity = quantity + (existing.quantity if existing else 0)
        await self._validate_product(product_id, new_quantity)
        await self.cart_repository.set_quantity(
            user_id=user_id,
            product_id=product_id,
            quantity=new_quantity,
        )
        return await self.get_cart(user_id)

    async def update_item(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
    ) -> CartResponse:
        if await self.cart_repository.get_item(user_id, product_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart item not found")
        await self._validate_product(product_id, quantity)
        await self.cart_repository.set_quantity(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
        )
        return await self.get_cart(user_id)

    async def remove_item(self, user_id: int, product_id: int) -> CartResponse:
        if not await self.cart_repository.remove_item(user_id, product_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart item not found")
        return await self.get_cart(user_id)

    async def clear(self, user_id: int) -> None:
        await self.cart_repository.clear(user_id)

    async def _validate_product(self, product_id: int, quantity: int) -> None:
        product = await self.product_repository.get_by_product_id(product_id)
        if product is None or not product.get("is_active"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not available")
        if product.get("price") is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Product has no price")
        if int(product.get("stock") or 0) < quantity:
            raise HTTPException(status.HTTP_409_CONFLICT, "Insufficient stock")
