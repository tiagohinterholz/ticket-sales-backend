import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class EventStatus(str, enum.Enum):
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"


class Event(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "events"

    organizer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    tmdb_movie_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    poster_url: Mapped[str | None] = mapped_column(String, nullable=True)
    venue: Mapped[str] = mapped_column(String, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(nullable=False)
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    seats_per_row: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status"), nullable=False
    )
