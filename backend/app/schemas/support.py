from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=180)
    category: str = Field(
        default="general",
        pattern=r"^(general|order|delivery|payment|product|return)$",
    )
    message: str = Field(min_length=3, max_length=3000)
    order_id: int | None = Field(default=None, ge=1)


class TicketReply(BaseModel):
    message: str = Field(min_length=2, max_length=3000)


class TicketStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(open|in_progress|resolved|closed)$")


class TicketPriorityUpdate(BaseModel):
    priority: str = Field(pattern=r"^(low|normal|high|urgent)$")


class TicketMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: int
    sender_role: str
    sender_name: str
    message: str
    created_at: datetime


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    order_id: int | None
    customer_name: str
    customer_email: str
    subject: str
    category: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    messages: list[TicketMessageResponse]


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SupportDashboardResponse(BaseModel):
    orders: int
    pending_orders: int
    delivered_orders: int
    open_tickets: int
    in_progress_tickets: int
