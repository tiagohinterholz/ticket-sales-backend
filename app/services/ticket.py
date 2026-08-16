from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ticket import Ticket


class TicketNotFoundError(Exception):
    pass


def get_owned_ticket(db: Session, ticket_id: UUID, owner_id: UUID) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.owner_id != owner_id:
        raise TicketNotFoundError("Ticket not found")
    return ticket


def list_for_owner(db: Session, owner_id: UUID) -> list[Ticket]:
    return list(db.execute(select(Ticket).where(Ticket.owner_id == owner_id)).scalars())
