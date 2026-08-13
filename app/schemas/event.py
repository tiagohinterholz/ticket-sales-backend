from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.event import EventStatus
from app.models.seat import SeatStatus
from app.schemas.base import BaseReadSchema


class EventCreate(BaseModel):
    movie_query: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    starts_at: datetime
    rows: int = Field(gt=0)
    seats_per_row: int = Field(gt=0)
    price_cents: int = Field(ge=0)

    @field_validator("starts_at")
    @classmethod
    def starts_at_must_be_in_the_future(cls, value: datetime) -> datetime:
        now = datetime.now(UTC)
        comparable_value = (
            value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        )
        if comparable_value <= now:
            raise ValueError("starts_at must be in the future")
        return value


class SeatRead(BaseReadSchema):
    row_label: str
    seat_number: int
    status: SeatStatus


class EventRead(BaseReadSchema):
    organizer_id: UUID
    tmdb_movie_id: int
    title: str
    poster_url: str | None
    venue: str
    starts_at: datetime
    rows: int
    seats_per_row: int
    capacity: int
    price_cents: int
    status: EventStatus


class EventDetailRead(EventRead):
    seats: list[SeatRead]


class EventListResponse(BaseModel):
    items: list[EventRead]
    total: int
