from datetime import datetime
from uuid import UUID

from app.models.ticket import TicketStatus
from app.schemas.base import BaseReadSchema


class TicketRead(BaseReadSchema):
    event_id: UUID
    seat_id: UUID
    owner_id: UUID
    status: TicketStatus
    held_at: datetime
    expires_at: datetime | None
