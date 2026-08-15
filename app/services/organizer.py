from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.seat import Seat
from app.models.ticket import Ticket, TicketStatus

SOLD_TICKET_STATUSES = (TicketStatus.PAID, TicketStatus.USED)


class EventNotOwnedError(Exception):
    pass


@dataclass
class OrganizerEventSummary:
    event: Event
    percent_sold: float


def _percent_sold(sold_count: int, capacity: int) -> float:
    if capacity == 0:
        return 0.0
    return sold_count / capacity


def _sold_counts_by_event(db: Session, event_ids: list[UUID]) -> dict[UUID, int]:
    if not event_ids:
        return {}
    rows = db.execute(
        select(Ticket.event_id, func.count(Ticket.id))
        .where(
            Ticket.event_id.in_(event_ids),
            Ticket.status.in_(SOLD_TICKET_STATUSES),
        )
        .group_by(Ticket.event_id)
    ).all()
    return dict(rows)


def list_organizer_events(
    db: Session, organizer_id: UUID
) -> list[OrganizerEventSummary]:
    events = list(
        db.execute(
            select(Event)
            .where(Event.organizer_id == organizer_id)
            .order_by(Event.starts_at)
        ).scalars()
    )
    sold_counts = _sold_counts_by_event(db, [event.id for event in events])
    return [
        OrganizerEventSummary(
            event=event,
            percent_sold=_percent_sold(sold_counts.get(event.id, 0), event.capacity),
        )
        for event in events
    ]


def get_organizer_event(db: Session, organizer_id: UUID, event_id: UUID) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.organizer_id != organizer_id:
        raise EventNotOwnedError("Event not found")
    return event


def get_event_seats(db: Session, event_id: UUID) -> list[Seat]:
    return list(
        db.execute(
            select(Seat)
            .where(Seat.event_id == event_id)
            .order_by(Seat.row_label, Seat.seat_number)
        ).scalars()
    )
