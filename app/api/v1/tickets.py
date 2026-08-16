from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.ticket import Ticket, TicketStatus
from app.models.user import Role, User
from app.schemas.ticket import TicketDetailRead, TicketRead
from app.services.booking import (
    CancelWindowError,
    InvalidTicketStateError,
    cancel_ticket,
)
from app.services.ticket import TicketNotFoundError, get_owned_ticket, list_for_owner
from app.services.ticketing import render_token

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _owned_ticket_or_404(db: Session, ticket_id: UUID, owner: User) -> Ticket:
    try:
        return get_owned_ticket(db, ticket_id, owner.id)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        ) from exc


@router.get("", response_model=list[TicketRead])
def list_my_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> list[Ticket]:
    return list_for_owner(db, current_user.id)


@router.get("/{ticket_id}", response_model=TicketDetailRead)
def get_ticket_detail(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> TicketDetailRead:
    ticket = _owned_ticket_or_404(db, ticket_id, current_user)

    qr_token = None
    if ticket.status == TicketStatus.PAID:
        qr_token = render_token(ticket)

    return TicketDetailRead(
        id=ticket.id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        event_id=ticket.event_id,
        seat_id=ticket.seat_id,
        owner_id=ticket.owner_id,
        status=ticket.status,
        held_at=ticket.held_at,
        expires_at=ticket.expires_at,
        qr_token=qr_token,
    )


@router.post("/{ticket_id}/cancel", response_model=TicketRead)
def cancel_ticket_endpoint(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> Ticket:
    ticket = _owned_ticket_or_404(db, ticket_id, current_user)
    try:
        return cancel_ticket(db, ticket, current_user)
    except CancelWindowError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cancellation is only allowed until 2 hours before the event",
        ) from exc
    except InvalidTicketStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
