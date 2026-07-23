from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.order import OrderRepository
from app.repositories.operations import OperationsRepository
from app.repositories.support import SupportRepository
from app.schemas.support import TicketCreate, TicketListResponse, TicketResponse


class SupportService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = SupportRepository(session)
        self.order_repository = OrderRepository(session)
        self.operations = OperationsRepository(session)
        self.session = session

    async def create_ticket(self, user: User, data: TicketCreate) -> TicketResponse:
        if data.order_id is not None:
            order = await self.order_repository.get_by_id(data.order_id, user_id=user.id)
            if order is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
        ticket = await self.repository.create_ticket(
            user_id=user.id,
            customer_name=user.full_name or user.email.split("@")[0],
            customer_email=user.email,
            subject=data.subject.strip(),
            category=data.category,
            order_id=data.order_id,
            message=data.message.strip(),
        )
        self.operations.add_audit(
            actor_id=user.id,
            actor_role=user.role,
            action="ticket.created",
            entity_type="ticket",
            entity_id=ticket.id,
            details={"category": ticket.category, "subject": ticket.subject},
        )
        for role in ("support", "admin"):
            self.operations.add_notification(
                target_role=role,
                notification_type="new_ticket",
                title="Nouvelle demande client",
                message=f"Ticket #{ticket.id}: {ticket.subject}",
                link=self._staff_ticket_link(role, ticket.id),
            )
        await self.session.commit()
        return TicketResponse.model_validate(ticket)

    async def list_tickets(
        self,
        *,
        page: int,
        page_size: int,
        user_id: int | None,
        ticket_status: str | None = None,
    ) -> TicketListResponse:
        tickets, total = await self.repository.list_tickets(
            page=page,
            page_size=page_size,
            user_id=user_id,
            ticket_status=ticket_status,
        )
        return TicketListResponse(
            items=[TicketResponse.model_validate(ticket) for ticket in tickets],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )

    async def get_ticket(
        self, ticket_id: int, *, user_id: int | None = None
    ) -> TicketResponse:
        ticket = await self.repository.get_ticket(ticket_id)
        if ticket is None or (user_id is not None and ticket.user_id != user_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        return TicketResponse.model_validate(ticket)

    async def reply(
        self, ticket_id: int, user: User, message: str, *, own_only: bool
    ) -> TicketResponse:
        ticket = await self.repository.get_ticket(ticket_id)
        if ticket is None or (own_only and ticket.user_id != user.id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        updated = await self.repository.add_message(
            ticket,
            sender_id=user.id,
            sender_role=user.role,
            sender_name=user.full_name or user.email.split("@")[0],
            message=message.strip(),
        )
        if user.role == "customer":
            for role in ("support", "admin"):
                self.operations.add_notification(
                    target_role=role,
                    notification_type="ticket_reply",
                    title="Reponse client",
                    message=f"Nouveau message sur le ticket #{ticket.id}",
                    link=self._staff_ticket_link(role, ticket.id),
                )
        else:
            self.operations.add_notification(
                user_id=ticket.user_id,
                notification_type="ticket_reply",
                title="Reponse du support",
                message=f"Le support a repondu au ticket #{ticket.id}",
                link=f"/help?ticket={ticket.id}",
            )
        self.operations.add_audit(
            actor_id=user.id,
            actor_role=user.role,
            action="ticket.message_added",
            entity_type="ticket",
            entity_id=ticket.id,
        )
        await self.session.commit()
        return TicketResponse.model_validate(updated)

    @staticmethod
    def _staff_ticket_link(role: str, ticket_id: int) -> str:
        if role == "admin":
            return f"/admin?tab=messages&ticket={ticket_id}"
        return f"/support?ticket={ticket_id}"

    async def set_status(
        self, ticket_id: int, value: str, actor: User | None = None
    ) -> TicketResponse:
        ticket = await self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        before = ticket.status
        updated = await self.repository.set_status(ticket, value)
        self.operations.add_audit(
            actor_id=actor.id if actor else None,
            actor_role=actor.role if actor else "system",
            action="ticket.status_updated",
            entity_type="ticket",
            entity_id=ticket.id,
            details={"before": before, "after": value},
        )
        self.operations.add_notification(
            user_id=ticket.user_id,
            notification_type="ticket_status",
            title="Mise a jour support",
            message=f"Ticket #{ticket.id}: {value}",
            link=f"/help?ticket={ticket.id}",
        )
        await self.session.commit()
        return TicketResponse.model_validate(updated)

    async def set_priority(
        self, ticket_id: int, value: str, actor: User | None = None
    ) -> TicketResponse:
        ticket = await self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        before = ticket.priority
        updated = await self.repository.set_priority(ticket, value)
        self.operations.add_audit(
            actor_id=actor.id if actor else None,
            actor_role=actor.role if actor else "system",
            action="ticket.priority_updated",
            entity_type="ticket",
            entity_id=ticket.id,
            details={"before": before, "after": value},
        )
        await self.session.commit()
        return TicketResponse.model_validate(updated)
