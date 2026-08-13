from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.event import Event, EventStatus
from app.models.seat import Seat, SeatStatus
from app.models.user import Role, User
from app.schemas.event import (
    EventCreate,
    EventDetailRead,
    EventListResponse,
    EventRead,
    SeatRead,
)
from app.services.catalog import CatalogUnavailableError, search_movies

router = APIRouter(prefix="/events", tags=["events"])


def _row_label(row_index: int) -> str:
    label = ""
    n = row_index + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        label = chr(65 + remainder) + label
    return label


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ORGANIZER)),
) -> Event:
    try:
        movies = search_movies(payload.movie_query)
    except CatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Movie catalog is unavailable, try again later",
        ) from exc

    if not movies:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No movie found for the given query",
        )
    movie = movies[0]

    event = Event(
        organizer_id=current_user.id,
        tmdb_movie_id=movie.tmdb_id,
        title=movie.title,
        poster_url=movie.poster_url,
        venue=payload.venue,
        starts_at=payload.starts_at,
        rows=payload.rows,
        seats_per_row=payload.seats_per_row,
        capacity=payload.rows * payload.seats_per_row,
        price_cents=payload.price_cents,
        status=EventStatus.PUBLISHED,
    )
    db.add(event)
    db.flush()

    seats = [
        Seat(
            event_id=event.id,
            row_label=_row_label(row_index),
            seat_number=seat_number,
            status=SeatStatus.AVAILABLE,
        )
        for row_index in range(payload.rows)
        for seat_number in range(1, payload.seats_per_row + 1)
    ]
    db.add_all(seats)

    db.commit()
    db.refresh(event)
    return event


@router.get("", response_model=EventListResponse)
def list_events(
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    db: Session = Depends(get_db),
) -> EventListResponse:
    stmt = select(Event).where(Event.status == EventStatus.PUBLISHED)
    if q:
        stmt = stmt.where(Event.title.ilike(f"%{q}%"))
    if date_from is not None:
        stmt = stmt.where(Event.starts_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Event.starts_at <= date_to)
    if price_min is not None:
        stmt = stmt.where(Event.price_cents >= price_min)
    if price_max is not None:
        stmt = stmt.where(Event.price_cents <= price_max)

    events = list(db.execute(stmt.order_by(Event.starts_at)).scalars().all())
    return EventListResponse(items=events, total=len(events))


@router.get("/{event_id}", response_model=EventDetailRead)
def get_event(event_id: UUID, db: Session = Depends(get_db)) -> EventDetailRead:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    seats = (
        db.execute(
            select(Seat)
            .where(Seat.event_id == event_id)
            .order_by(Seat.row_label, Seat.seat_number)
        )
        .scalars()
        .all()
    )

    return EventDetailRead(
        **EventRead.model_validate(event).model_dump(),
        seats=[SeatRead.model_validate(seat) for seat in seats],
    )
