from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.support_ticket import SupportMessage, SupportTicket


class SupportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_ticket(
        self,
        *,
        user_id: int,
        customer_name: str,
        customer_email: str,
        subject: str,
        category: str,
        order_id: int | None,
        message: str,
    ) -> SupportTicket:
        ticket = SupportTicket(
            user_id=user_id,
            order_id=order_id,
            customer_name=customer_name,
            customer_email=customer_email,
            subject=subject,
            category=category,
            messages=[
                SupportMessage(
                    sender_id=user_id,
                    sender_role="customer",
                    sender_name=customer_name,
                    message=message,
                )
            ],
        )
        self.session.add(ticket)
        await self.session.commit()
        return await self.get_ticket(ticket.id)

    async def get_ticket(self, ticket_id: int) -> SupportTicket | None:
        result = await self.session.execute(
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages))
            .where(SupportTicket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def list_tickets(
        self,
        *,
        page: int,
        page_size: int,
        user_id: int | None = None,
        ticket_status: str | None = None,
    ) -> tuple[list[SupportTicket], int]:
        conditions = []
        if user_id is not None:
            conditions.append(SupportTicket.user_id == user_id)
        if ticket_status:
            conditions.append(SupportTicket.status == ticket_status)
        total = int(
            (
                await self.session.execute(
                    select(func.count(SupportTicket.id)).where(*conditions)
                )
            ).scalar_one()
        )
        result = await self.session.execute(
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages))
            .where(*conditions)
            .order_by(SupportTicket.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def add_message(
        self,
        ticket: SupportTicket,
        *,
        sender_id: int,
        sender_role: str,
        sender_name: str,
        message: str,
    ) -> SupportTicket:
        self.session.add(
            SupportMessage(
                ticket_id=ticket.id,
                sender_id=sender_id,
                sender_role=sender_role,
                sender_name=sender_name,
                message=message,
            )
        )
        if sender_role == "customer" and ticket.status in {"resolved", "closed"}:
            ticket.status = "open"
        elif sender_role in {"support", "admin"} and ticket.status == "open":
            ticket.status = "in_progress"
        ticket.updated_at = datetime.now(UTC)
        await self.session.commit()
        return await self.get_ticket(ticket.id)

    async def set_status(self, ticket: SupportTicket, value: str) -> SupportTicket:
        ticket.status = value
        ticket.updated_at = datetime.now(UTC)
        await self.session.commit()
        return await self.get_ticket(ticket.id)

    async def set_priority(self, ticket: SupportTicket, value: str) -> SupportTicket:
        ticket.priority = value
        ticket.updated_at = datetime.now(UTC)
        await self.session.commit()
        return await self.get_ticket(ticket.id)

    async def dashboard_counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for value, key in (("open", "open_tickets"), ("in_progress", "in_progress_tickets")):
            result[key] = int(
                (
                    await self.session.execute(
                        select(func.count(SupportTicket.id)).where(
                            SupportTicket.status == value
                        )
                    )
                ).scalar_one()
            )
        return result
