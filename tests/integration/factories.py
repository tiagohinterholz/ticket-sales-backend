import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.event import Event, EventStatus
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.user import Role, User


def make_user(db_session: Session, role: Role, email: str | None = None) -> User:
    user = User(
        email=email or f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        password_hash=hash_password("irrelevant"),
        role=role,
        name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def make_event(db_session: Session, organizer: User, **overrides) -> Event:
    defaults = {
        "organizer_id": organizer.id,
        "tmdb_movie_id": uuid.uuid4().int % 1_000_000,
        "title": f"Movie {uuid.uuid4()}",
        "poster_url": None,
        "venue": "Test Venue",
        "starts_at": datetime.now(UTC) + timedelta(days=7),
        "rows": 1,
        "seats_per_row": 1,
        "capacity": 1,
        "price_cents": 1000,
        "status": EventStatus.PUBLISHED,
    }
    defaults.update(overrides)
    event = Event(**defaults)
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


def make_seat(
    db_session: Session,
    event: Event,
    status: SeatStatus = SeatStatus.AVAILABLE,
    row_label: str = "A",
    seat_number: int = 1,
) -> Seat:
    seat = Seat(
        event_id=event.id,
        row_label=row_label,
        seat_number=seat_number,
        status=status,
    )
    db_session.add(seat)
    db_session.commit()
    db_session.refresh(seat)
    return seat


def make_ticket(
    db_session: Session,
    event: Event,
    seat: Seat,
    owner: User,
    status: TicketStatus = TicketStatus.HELD,
    **overrides,
) -> Ticket:
    defaults = {
        "event_id": event.id,
        "seat_id": seat.id,
        "owner_id": owner.id,
        "status": status,
        "qr_secret": uuid.uuid4().hex,
        "held_at": datetime.now(UTC),
        "expires_at": None,
        "paid_at": None,
        "used_at": None,
        "cancelled_at": None,
    }
    defaults.update(overrides)
    ticket = Ticket(**defaults)
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)
    return ticket
