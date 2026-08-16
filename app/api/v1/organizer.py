from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.event import EventDetailRead, EventRead, SeatRead
from app.schemas.organizer import OrganizerEventRead
from app.services.organizer import (
    EventNotOwnedError,
    get_organizer_event,
    list_organizer_events,
)
from app.services.seat import list_for_event

router = APIRouter(prefix="/organizer", tags=["organizer"])


@router.get("/events", response_model=list[OrganizerEventRead])
def list_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ORGANIZER)),
) -> list[OrganizerEventRead]:
    summaries = list_organizer_events(db, current_user.id)
    return [
        OrganizerEventRead(
            **EventRead.model_validate(summary.event).model_dump(),
            percent_sold=summary.percent_sold,
        )
        for summary in summaries
    ]


@router.get("/events/{event_id}/seats", response_model=EventDetailRead)
def get_event_seat_map(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ORGANIZER)),
) -> EventDetailRead:
    try:
        event = get_organizer_event(db, current_user.id, event_id)
    except EventNotOwnedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        ) from exc

    seats = list_for_event(db, event_id)
    return EventDetailRead(
        **EventRead.model_validate(event).model_dump(),
        seats=[SeatRead.model_validate(seat) for seat in seats],
    )
