import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class TicketStatus(str, enum.Enum):
    HELD = "HELD"
    PAID = "PAID"
    USED = "USED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    TRANSFERRED = "TRANSFERRED"


class Ticket(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "tickets"

    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"), nullable=False)
    seat_id: Mapped[UUID] = mapped_column(ForeignKey("seats.id"), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status"), nullable=False
    )
    qr_secret: Mapped[str] = mapped_column(String, nullable=False)

    # Domain-state timestamps — each marks a distinct business transition,
    # kept explicit rather than folded into the generic TimestampMixin fields.
    held_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)
