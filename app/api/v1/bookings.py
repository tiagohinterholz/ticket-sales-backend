from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.ticket import Ticket
from app.models.user import Role, User
from app.schemas.ticket import TicketRead
from app.services.booking import SeatUnavailableError, hold_seat

router = APIRouter(prefix="/events", tags=["bookings"])


@router.post(
    "/{event_id}/seats/{seat_id}/hold",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
)
def hold_seat_endpoint(
    event_id: UUID,
    seat_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> Ticket:
    try:
        return hold_seat(db, event_id, seat_id, current_user.id)
    except SeatUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Seat is not available"
        ) from exc
