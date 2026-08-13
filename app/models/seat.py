import enum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class SeatStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    HOLD = "HOLD"
    SOLD = "SOLD"


class Seat(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "row_label", "seat_number", name="uq_seat_event_row_number"
        ),
    )

    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"), nullable=False)
    row_label: Mapped[str] = mapped_column(String, nullable=False)
    seat_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SeatStatus] = mapped_column(
        Enum(SeatStatus, name="seat_status"), nullable=False
    )
    current_ticket_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tickets.id"), nullable=True
    )
