from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event, EventStatus
from app.models.seat import Seat, SeatStatus
from app.services import seat as seat_service
from app.services.catalog import MovieResult, search_movies


class NoMovieFoundError(Exception):
    pass


class MovieNotInResultsError(Exception):
    pass


def row_label(row_index: int) -> str:
    label = ""
    n = row_index + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        label = chr(65 + remainder) + label
    return label


def _resolve_movie(movie_query: str, tmdb_movie_id: int | None) -> MovieResult:
    movies = search_movies(movie_query)
    if not movies:
        raise NoMovieFoundError("No movie found for the given query")

    if tmdb_movie_id is None:
        return movies[0]

    movie = next((m for m in movies if m.tmdb_id == tmdb_movie_id), None)
    if movie is None:
        raise MovieNotInResultsError(
            "Selected movie is not among the current search results, search again"
        )
    return movie


def create_event(
    db: Session,
    organizer_id: UUID,
    movie_query: str,
    tmdb_movie_id: int | None,
    venue: str,
    starts_at: datetime,
    rows: int,
    seats_per_row: int,
    price_cents: int,
) -> Event:
    movie = _resolve_movie(movie_query, tmdb_movie_id)

    event = Event(
        organizer_id=organizer_id,
        tmdb_movie_id=movie.tmdb_id,
        title=movie.title,
        poster_url=movie.poster_url,
        venue=venue,
        starts_at=starts_at,
        rows=rows,
        seats_per_row=seats_per_row,
        capacity=rows * seats_per_row,
        price_cents=price_cents,
        status=EventStatus.PUBLISHED,
    )
    db.add(event)
    db.flush()

    seats = [
        Seat(
            event_id=event.id,
            row_label=row_label(row_index),
            seat_number=seat_number,
            status=SeatStatus.AVAILABLE,
        )
        for row_index in range(rows)
        for seat_number in range(1, seats_per_row + 1)
    ]
    db.add_all(seats)

    db.commit()
    db.refresh(event)
    return event


def list_events(
    db: Session,
    q: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    price_min: int | None,
    price_max: int | None,
) -> list[Event]:
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

    return list(db.execute(stmt.order_by(Event.starts_at)).scalars().all())


def get_event_with_seats(
    db: Session, event_id: UUID
) -> tuple[Event, list[Seat]] | None:
    event = db.get(Event, event_id)
    if event is None:
        return None

    return event, seat_service.list_for_event(db, event_id)
