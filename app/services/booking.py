import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event import Event
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User


class SeatUnavailableError(Exception):
    pass


class CancelWindowError(Exception):
    pass


class InvalidTicketStateError(Exception):
    pass


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def hold_seat(db: Session, event_id, seat_id, user_id) -> Ticket:
    result = db.execute(
        update(Seat)
        .where(
            Seat.id == seat_id,
            Seat.event_id == event_id,
            Seat.status == SeatStatus.AVAILABLE,
        )
        .values(status=SeatStatus.HOLD)
    )
    if result.rowcount == 0:
        db.rollback()
        raise SeatUnavailableError("Seat is not available")

    now = datetime.now(UTC)
    ticket = Ticket(
        event_id=event_id,
        seat_id=seat_id,
        owner_id=user_id,
        status=TicketStatus.HELD,
        qr_secret=secrets.token_hex(32),
        held_at=now,
        expires_at=now + timedelta(minutes=settings.SEAT_HOLD_MINUTES),
    )
    db.add(ticket)
    db.flush()

    db.execute(
        update(Seat).where(Seat.id == seat_id).values(current_ticket_id=ticket.id)
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def sweep_expired_holds(db: Session, event_id=None) -> int:
    now = datetime.now(UTC)
    stmt = select(Ticket).where(
        Ticket.status == TicketStatus.HELD, Ticket.expires_at < now
    )
    if event_id is not None:
        stmt = stmt.where(Ticket.event_id == event_id)

    expired_tickets = list(db.execute(stmt).scalars().all())
    for ticket in expired_tickets:
        ticket.status = TicketStatus.EXPIRED
        db.execute(
            update(Seat)
            .where(Seat.id == ticket.seat_id)
            .values(status=SeatStatus.AVAILABLE, current_ticket_id=None)
        )
    db.commit()
    return len(expired_tickets)


def cancel_ticket(db: Session, ticket: Ticket, actor: User) -> Ticket:
    if ticket.status != TicketStatus.PAID:
        raise InvalidTicketStateError(
            f"Cannot cancel ticket in status {ticket.status.value}"
        )

    event = db.get(Event, ticket.event_id)
    now = datetime.now(UTC)
    if _as_utc(event.starts_at) - now < timedelta(hours=settings.CANCEL_WINDOW_HOURS):
        raise CancelWindowError("Cancellation window has passed")

    ticket.status = TicketStatus.CANCELLED
    ticket.cancelled_at = now
    db.execute(
        update(Seat)
        .where(Seat.id == ticket.seat_id)
        .values(status=SeatStatus.AVAILABLE, current_ticket_id=None)
    )
    db.commit()
    db.refresh(ticket)
    return ticket
