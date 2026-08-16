from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.event import Event
from app.models.user import Role, User
from app.schemas.catalog import MovieSearchResult
from app.schemas.event import (
    EventCreate,
    EventDetailRead,
    EventListResponse,
    EventRead,
    SeatRead,
)
from app.services import event as event_service
from app.services.catalog import CatalogUnavailableError, search_movies

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/catalog", response_model=list[MovieSearchResult])
def search_catalog(
    query: str,
    current_user: User = Depends(require_role(Role.ORGANIZER)),
) -> list[MovieSearchResult]:
    try:
        movies = search_movies(query)
    except CatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Movie catalog is unavailable, try again later",
        ) from exc

    return [
        MovieSearchResult(
            tmdb_id=movie.tmdb_id,
            title=movie.title,
            poster_url=movie.poster_url,
            release_date=movie.release_date,
        )
        for movie in movies
    ]


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ORGANIZER)),
) -> Event:
    try:
        return event_service.create_event(
            db,
            organizer_id=current_user.id,
            movie_query=payload.movie_query,
            tmdb_movie_id=payload.tmdb_movie_id,
            venue=payload.venue,
            starts_at=payload.starts_at,
            rows=payload.rows,
            seats_per_row=payload.seats_per_row,
            price_cents=payload.price_cents,
        )
    except CatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Movie catalog is unavailable, try again later",
        ) from exc
    except event_service.NoMovieFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except event_service.MovieNotInResultsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("", response_model=EventListResponse)
def list_events(
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    db: Session = Depends(get_db),
) -> EventListResponse:
    events = event_service.list_events(
        db, q, date_from, date_to, price_min, price_max
    )
    return EventListResponse(items=events, total=len(events))


@router.get("/{event_id}", response_model=EventDetailRead)
def get_event(event_id: UUID, db: Session = Depends(get_db)) -> EventDetailRead:
    result = event_service.get_event_with_seats(db, event_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    event, seats = result
    return EventDetailRead(
        **EventRead.model_validate(event).model_dump(),
        seats=[SeatRead.model_validate(seat) for seat in seats],
    )
