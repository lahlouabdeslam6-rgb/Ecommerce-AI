import hashlib
import secrets

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.repositories.operations import OperationsRepository
from app.repositories.product import ProductRepository
from app.schemas.order import (
    CheckoutRequest,
    GuestCheckoutRequest,
    GuestCheckoutResponse,
    OrderListResponse,
    OrderResponse,
)


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

    async def checkout(
        self,
        user_id: int,
        email: str,
        data: CheckoutRequest,
    ) -> OrderResponse:
        cart_items = await self.cart_repository.list_items(user_id)
        order = await self._checkout_items(
            user_id=user_id,
            email=email,
            data=data,
            requested_items=[
                (item.product_id, item.quantity) for item in cart_items
            ],
        )
        await self.cart_repository.clear(user_id, commit=False)
        await self.session.commit()
        return order

    async def guest_checkout(
        self,
        data: GuestCheckoutRequest,
    ) -> GuestCheckoutResponse:
        tracking_token = secrets.token_urlsafe(32)
        order = await self._checkout_items(
            user_id=None,
            email=str(data.email),
            data=data,
            requested_items=[
                (item.product_id, item.quantity) for item in data.items
            ],
            guest_token_hash=self._token_hash(tracking_token),
        )
        await self.session.commit()
        return GuestCheckoutResponse(
            order=order,
            tracking_token=tracking_token,
        )

    async def track_guest_order(
        self,
        order_id: int,
        tracking_token: str,
    ) -> OrderResponse:
        order = await self.order_repository.get_by_id(order_id)
        if (
            order is None
            or order.user_id is not None
            or order.guest_token_hash is None
            or not secrets.compare_digest(
                order.guest_token_hash,
                self._token_hash(tracking_token),
            )
        ):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Commande invitée introuvable",
            )
        return OrderResponse.model_validate(order)

    async def _checkout_items(
        self,
        *,
        user_id: int | None,
        email: str,
        data: CheckoutRequest,
        requested_items: list[tuple[int, int]],
        guest_token_hash: str | None = None,
    ) -> OrderResponse:
        if data.payment_method == "card" and (
            not data.payment_token
            or not data.payment_token.startswith("demo_")
            or not data.card_last4
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Card payment could not be authorized",
            )
        if not requested_items:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le panier est vide")

        quantities: dict[int, int] = {}
        for product_id, quantity in requested_items:
            quantities[product_id] = min(
                quantities.get(product_id, 0) + quantity,
                99,
            )

        products = await self.product_repository.get_many_by_ids(
            list(quantities)
        )
        order_items: list[dict[str, object]] = []
        subtotal = 0.0

        for product_id, quantity in quantities.items():
            product = products.get(product_id)
            if product is None or not product.get("is_active"):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Le produit {product_id} est indisponible",
                )
            if int(product.get("stock") or 0) < quantity:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Stock insuffisant pour le produit {product_id}",
                )
            unit_price = float(product.get("price") or 0)
            line_subtotal = round(unit_price * quantity, 2)
            images = product.get("images") or []
            order_items.append(
                {
                    "product_id": product_id,
                    "product_name": product.get("name") or "Unnamed product",
                    "brand": product.get("brand"),
                    "image_url": images[0] if images else None,
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "subtotal": line_subtotal,
                }
            )
            subtotal += line_subtotal

        reserved: list[tuple[int, int]] = []
        try:
            for product_id, quantity in quantities.items():
                if not await self.product_repository.reserve_stock(
                    product_id, quantity
                ):
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        f"Le stock du produit {product_id} a changé",
                    )
                reserved.append((product_id, quantity))

            order = await self.order_repository.create(
                user_id=user_id,
                email=email,
                guest_token_hash=guest_token_hash,
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
                actor_role="customer" if user_id is not None else "guest",
                action="order.created",
                entity_type="order",
                entity_id=order.id,
                details={
                    "total": order.total,
                    "payment_method": order.payment_method,
                    "guest": user_id is None,
                },
            )
            confirmation_message = (
                f"Commande #{order.id} à confirmer par téléphone : "
                f"{order.full_name}, {order.phone}, {order.city}"
            )
            self.operations.add_notification(
                target_role="admin",
                notification_type="new_order",
                title="Nouvelle commande à confirmer",
                message=f"{confirmation_message} ({order.total} MAD)",
                link=f"/admin?tab=orders&order={order.id}",
            )
            self.operations.add_notification(
                target_role="support",
                notification_type="new_order",
                title="Nouvelle commande à confirmer",
                message=confirmation_message,
                link=f"/support?tab=orders&order={order.id}",
            )
            await self.session.flush()
            saved_order = await self.order_repository.get_by_id(
                order.id,
                user_id=user_id,
            )
            if saved_order is None:
                raise RuntimeError("Order was not saved")
            return OrderResponse.model_validate(saved_order)
        except Exception:
            await self.session.rollback()
            for product_id, quantity in reserved:
                await self.product_repository.restore_stock(product_id, quantity)
            raise

    @staticmethod
    def _token_hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

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
        if order.user_id is not None:
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
