from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.repositories.operations import OperationsRepository
from app.repositories.product import ProductRepository
from app.schemas.order import CheckoutRequest, OrderListResponse, OrderResponse


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"shipped", "cancelled"},
    "shipped": {"delivered", "delivery_failed"},
    "delivery_failed": {"shipped", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cart_repository = CartRepository(session)
        self.order_repository = OrderRepository(session)
        self.operations = OperationsRepository(session)
        self.product_repository = ProductRepository()

    async def checkout(self, user_id: int, data: CheckoutRequest) -> OrderResponse:
        if data.payment_method == "card" and (
            not data.payment_token
            or not data.payment_token.startswith("demo_")
            or not data.card_last4
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Card payment could not be authorized",
            )
        cart_items = await self.cart_repository.list_items(user_id)
        if not cart_items:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

        products = await self.product_repository.get_many_by_ids(
            [item.product_id for item in cart_items]
        )
        order_items: list[dict[str, object]] = []
        subtotal = 0.0

        for cart_item in cart_items:
            product = products.get(cart_item.product_id)
            if product is None or not product.get("is_active"):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Product {cart_item.product_id} is unavailable",
                )
            if int(product.get("stock") or 0) < cart_item.quantity:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Insufficient stock for product {cart_item.product_id}",
                )
            unit_price = float(product.get("price") or 0)
            line_subtotal = round(unit_price * cart_item.quantity, 2)
            images = product.get("images") or []
            order_items.append(
                {
                    "product_id": cart_item.product_id,
                    "product_name": product.get("name") or "Unnamed product",
                    "brand": product.get("brand"),
                    "image_url": images[0] if images else None,
                    "unit_price": unit_price,
                    "quantity": cart_item.quantity,
                    "subtotal": line_subtotal,
                }
            )
            subtotal += line_subtotal

        reserved: list[tuple[int, int]] = []
        try:
            for cart_item in cart_items:
                if not await self.product_repository.reserve_stock(
                    cart_item.product_id, cart_item.quantity
                ):
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        f"Stock changed for product {cart_item.product_id}",
                    )
                reserved.append((cart_item.product_id, cart_item.quantity))

            order = await self.order_repository.create(
                user_id=user_id,
                shipping=data.model_dump(
                    include={"full_name", "phone", "address", "city", "notes"}
                ),
                items=order_items,
                subtotal=round(subtotal, 2),
                delivery_fee=0,
                payment_method=data.payment_method,
                payment_status=(
                    "paid" if data.payment_method == "card" else "pending"
                ),
                card_last4=(data.card_last4 if data.payment_method == "card" else None),
                card_brand=(data.card_brand if data.payment_method == "card" else None),
                payment_reference=(
                    data.payment_token if data.payment_method == "card" else None
                ),
            )
            for item in order_items:
                before = int(products[int(item["product_id"])].get("stock") or 0)
                quantity = int(item["quantity"])
                self.operations.add_stock_movement(
                    product_id=int(item["product_id"]),
                    product_name=str(item["product_name"]),
                    movement_type="order_reserved",
                    quantity=-quantity,
                    stock_before=before,
                    stock_after=before - quantity,
                    actor_id=user_id,
                    reference_type="order",
                    reference_id=order.id,
                )
            self.operations.add_audit(
                actor_id=user_id,
                actor_role="customer",
                action="order.created",
                entity_type="order",
                entity_id=order.id,
                details={"total": order.total, "payment_method": order.payment_method},
            )
            self.operations.add_notification(
                target_role="admin",
                notification_type="new_order",
                title="Nouvelle commande",
                message=f"Commande #{order.id} creee ({order.total} MAD)",
                link=f"/admin?order={order.id}",
            )
            self.operations.add_notification(
                target_role="support",
                notification_type="new_order",
                title="Nouvelle commande",
                message=f"Commande #{order.id} creee",
                link=f"/support?order={order.id}",
            )
            await self.cart_repository.clear(user_id, commit=False)
            await self.session.commit()
            saved_order = await self.order_repository.get_by_id(
                order.id, user_id=user_id
            )
            if saved_order is None:
                raise RuntimeError("Order was not saved")
            return OrderResponse.model_validate(saved_order)
        except Exception:
            await self.session.rollback()
            for product_id, quantity in reserved:
                await self.product_repository.restore_stock(product_id, quantity)
            raise

    async def list_orders(
        self,
        *,
        user_id: int | None,
        page: int,
        page_size: int,
        order_status: str | None = None,
    ) -> OrderListResponse:
        orders, total = await self.order_repository.list_orders(
            user_id=user_id,
            page=page,
            page_size=page_size,
            order_status=order_status,
        )
        return OrderListResponse(
            items=[OrderResponse.model_validate(order) for order in orders],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )

    async def get_order(self, order_id: int, user_id: int | None) -> OrderResponse:
        order = await self.order_repository.get_by_id(order_id, user_id=user_id)
        if order is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
        return OrderResponse.model_validate(order)

    async def cancel_client_order(self, order_id: int, user_id: int) -> OrderResponse:
        order = await self.order_repository.get_by_id(order_id, user_id=user_id)
        if order is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
        if order.order_status not in {"pending", "confirmed"}:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This order can no longer be cancelled",
            )
        await self._restore_order_stock(order)
        self.operations.add_audit(
            actor_id=user_id,
            actor_role="customer",
            action="order.cancelled",
            entity_type="order",
            entity_id=order.id,
        )
        self.operations.add_notification(
            target_role="admin",
            notification_type="order_cancelled",
            title="Commande annulee",
            message=f"Le client a annule la commande #{order.id}",
            link=f"/admin?order={order.id}",
        )
        updated = await self.order_repository.update_status(order, "cancelled")
        return OrderResponse.model_validate(updated)

    async def update_admin_status(
        self,
        order_id: int,
        new_status: str,
        actor_id: int | None = None,
        actor_role: str = "admin",
    ) -> OrderResponse:
        order = await self.order_repository.get_by_id(order_id)
        if order is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
        if new_status not in ALLOWED_TRANSITIONS.get(order.order_status, set()):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Cannot change {order.order_status} to {new_status}",
            )
        if new_status == "cancelled":
            await self._restore_order_stock(order)
        previous_status = order.order_status
        self.operations.add_audit(
            actor_id=actor_id,
            actor_role=actor_role,
            action="order.status_updated",
            entity_type="order",
            entity_id=order.id,
            details={"before": previous_status, "after": new_status},
        )
        self.operations.add_notification(
            user_id=order.user_id,
            notification_type="order_status",
            title="Mise a jour commande",
            message=f"Commande #{order.id}: {new_status}",
            link=f"/orders?order={order.id}",
        )
        updated = await self.order_repository.update_status(order, new_status)
        return OrderResponse.model_validate(updated)

    async def _restore_order_stock(self, order: Order) -> None:
        for item in order.items:
            product = await self.product_repository.get_by_product_id(item.product_id)
            before = int(product.get("stock") or 0) if product else 0
            await self.product_repository.restore_stock(item.product_id, item.quantity)
            self.operations.add_stock_movement(
                product_id=item.product_id,
                product_name=item.product_name,
                movement_type="order_restored",
                quantity=item.quantity,
                stock_before=before,
                stock_after=before + item.quantity,
                reference_type="order",
                reference_id=order.id,
            )
