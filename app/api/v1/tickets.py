from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.ticket import Ticket, TicketStatus
from app.models.user import Role, User
from app.schemas.ticket import TicketDetailRead, TicketRead
from app.services import ticketing

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _get_owned_ticket(db: Session, ticket_id: UUID, owner: User) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        )
    return ticket


@router.get("", response_model=list[TicketRead])
def list_my_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> list[Ticket]:
    return list(
        db.execute(
            select(Ticket).where(Ticket.owner_id == current_user.id)
        ).scalars()
    )


@router.get("/{ticket_id}", response_model=TicketDetailRead)
def get_ticket_detail(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> TicketDetailRead:
    ticket = _get_owned_ticket(db, ticket_id, current_user)

    qr_token = None
    if ticket.status == TicketStatus.PAID:
        qr_token = ticketing.issue(ticket)
        db.commit()
        db.refresh(ticket)

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
