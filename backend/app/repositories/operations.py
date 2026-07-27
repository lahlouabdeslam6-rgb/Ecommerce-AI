import json
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import AuditLog, Notification, StockMovement
from app.models.user import User


class OperationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add_audit(
        self,
        *,
        actor_id: int | None,
        actor_role: str,
        action: str,
        entity_type: str,
        entity_id: str | int | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        item = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=json.dumps(details, ensure_ascii=False, default=str)
            if details
            else None,
        )
        self.session.add(item)
        return item

    def add_stock_movement(
        self,
        *,
        product_id: int,
        product_name: str,
        movement_type: str,
        quantity: int,
        stock_before: int,
        stock_after: int,
        actor_id: int | None = None,
        reference_type: str | None = None,
        reference_id: str | int | None = None,
        note: str | None = None,
    ) -> StockMovement:
        item = StockMovement(
            product_id=product_id,
            product_name=product_name,
            movement_type=movement_type,
            quantity=quantity,
            stock_before=stock_before,
            stock_after=stock_after,
            actor_id=actor_id,
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id is not None else None,
            note=note,
        )
        self.session.add(item)
        return item

    def add_notification(
        self,
        *,
        notification_type: str,
        title: str,
        message: str,
        user_id: int | None = None,
        target_role: str | None = None,
        link: str | None = None,
    ) -> Notification:
        item = Notification(
            user_id=user_id,
            target_role=target_role,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )
        self.session.add(item)
        return item

    async def list_audit(
        self, page: int, page_size: int
    ) -> tuple[list[tuple[AuditLog, str | None]], int]:
        total = int(
            (await self.session.execute(select(func.count(AuditLog.id)))).scalar_one()
        )
        result = await self.session.execute(
            select(AuditLog, User.email)
            .outerjoin(User, User.id == AuditLog.actor_id)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [(row[0], row[1]) for row in result.all()], total

    async def list_orchestrator_runs(
        self,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[AuditLog, str | None]], int]:
        condition = AuditLog.entity_type == "ai_orchestrator"
        total = int(
            (
                await self.session.execute(
                    select(func.count(AuditLog.id)).where(condition)
                )
            ).scalar_one()
        )
        result = await self.session.execute(
            select(AuditLog, User.email)
            .outerjoin(User, User.id == AuditLog.actor_id)
            .where(condition)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [(row[0], row[1]) for row in result.all()], total

    async def list_stock(
        self, page: int, page_size: int, product_id: int | None = None
    ) -> tuple[list[StockMovement], int]:
        condition = StockMovement.product_id == product_id if product_id else True
        total = int(
            (
                await self.session.execute(
                    select(func.count(StockMovement.id)).where(condition)
                )
            ).scalar_one()
        )
        result = await self.session.execute(
            select(StockMovement)
            .where(condition)
            .order_by(StockMovement.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_notifications(
        self, *, user_id: int, role: str, limit: int = 50
    ) -> tuple[list[Notification], int]:
        visible = or_(
            Notification.user_id == user_id,
            Notification.target_role == role,
        )
        result = await self.session.execute(
            select(Notification)
            .where(visible)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        unread = int(
            (
                await self.session.execute(
                    select(func.count(Notification.id)).where(
                        visible, Notification.is_read.is_(False)
                    )
                )
            ).scalar_one()
        )
        return list(result.scalars().all()), unread

    async def mark_read(self, notification_id: int, user_id: int, role: str) -> bool:
        result = await self.session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                or_(
                    Notification.user_id == user_id,
                    Notification.target_role == role,
                ),
            )
        )
        item = result.scalar_one_or_none()
        if item is None:
            return False
        item.is_read = True
        await self.session.commit()
        return True
