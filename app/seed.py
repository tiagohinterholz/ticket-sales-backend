from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.event import Event, EventStatus
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.user import Role, User
from app.services import ticketing
from app.services.catalog import CatalogUnavailableError, search_movies
from app.services.event import row_label as compute_row_label

FALLBACK_TMDB_MOVIE_ID = 0

USERS = [
    (
        "organizador1@ticketsales.dev",
        "organizador123",
        Role.ORGANIZER,
        "Organizador Um",
    ),
    (
        "organizador2@ticketsales.dev",
        "organizador123",
        Role.ORGANIZER,
        "Organizador Dois",
    ),
    ("cliente1@ticketsales.dev", "cliente123", Role.CUSTOMER, "Cliente Um"),
    ("cliente2@ticketsales.dev", "cliente123", Role.CUSTOMER, "Cliente Dois"),
    ("cliente3@ticketsales.dev", "cliente123", Role.CUSTOMER, "Cliente Tres"),
    ("cliente4@ticketsales.dev", "cliente123", Role.CUSTOMER, "Cliente Quatro"),
    (
        "portaria1@ticketsales.dev",
        "portaria123",
        Role.GATE_STAFF,
        "Operador de Portaria Um",
    ),
    (
        "portaria2@ticketsales.dev",
        "portaria123",
        Role.GATE_STAFF,
        "Operador de Portaria Dois",
    ),
]


@dataclass
class SeatOverride:
    row_label: str
    seat_number: int
    seat_status: SeatStatus
    ticket_status: TicketStatus | None
    customer_email: str | None


@dataclass
class EventSpec:
    organizer_email: str
    movie_query: str
    venue: str
    rows: int
    seats_per_row: int
    price_cents: int
    days_from_now: int
    overrides: list[SeatOverride] = field(default_factory=list)


EVENT_SPECS = [
    EventSpec(
        organizer_email="organizador1@ticketsales.dev",
        movie_query="Interstellar",
        venue="Sala 1 - Cinema Central",
        rows=3,
        seats_per_row=5,
        price_cents=4500,
        days_from_now=7,
        overrides=[
            SeatOverride(
                "A", 1, SeatStatus.HOLD, TicketStatus.HELD, "cliente1@ticketsales.dev"
            ),
            SeatOverride(
                "A", 2, SeatStatus.SOLD, TicketStatus.PAID, "cliente2@ticketsales.dev"
            ),
        ],
    ),
    EventSpec(
        organizer_email="organizador1@ticketsales.dev",
        movie_query="The Dark Knight",
        venue="Sala 2 - Cinema Central",
        rows=2,
        seats_per_row=6,
        price_cents=4000,
        days_from_now=10,
        overrides=[
            SeatOverride(
                "A", 1, SeatStatus.SOLD, TicketStatus.PAID, "cliente3@ticketsales.dev"
            ),
        ],
    ),
    EventSpec(
        organizer_email="organizador2@ticketsales.dev",
        movie_query="Oppenheimer",
        venue="Sala 1 - Multiplex Norte",
        rows=4,
        seats_per_row=4,
        price_cents=5000,
        days_from_now=14,
        overrides=[
            SeatOverride(
                "B", 2, SeatStatus.HOLD, TicketStatus.HELD, "cliente4@ticketsales.dev"
            ),
        ],
    ),
    EventSpec(
        organizer_email="organizador2@ticketsales.dev",
        movie_query="Barbie",
        venue="Sala 2 - Multiplex Norte",
        rows=2,
        seats_per_row=4,
        price_cents=3500,
        days_from_now=5,
        overrides=[],
    ),
]


def _get_or_create_user(
    db: Session, email: str, password: str, role: Role, name: str
) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        email=email, password_hash=hash_password(password), role=role, name=name
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _resolve_movie(query: str) -> tuple[int, str, str | None]:
    try:
        results = search_movies(query)
    except CatalogUnavailableError:
        print(
            f"WARNING: TMDb catalog unavailable, seeding event for {query!r} without a real poster"
        )
        return FALLBACK_TMDB_MOVIE_ID, query, None

    for result in results:
        if result.title.lower() == query.lower():
            return result.tmdb_id, result.title, result.poster_url

    if results:
        first = results[0]
        return first.tmdb_id, first.title, first.poster_url

    print(
        f"WARNING: TMDb returned no results for {query!r}, seeding event without a real poster"
    )
    return FALLBACK_TMDB_MOVIE_ID, query, None


def _create_event_with_seats(
    db: Session, spec: EventSpec, organizer: User, users_by_email: dict[str, User]
) -> tuple[Event, str | None]:
    tmdb_movie_id, title, poster_url = _resolve_movie(spec.movie_query)

    event = Event(
        organizer_id=organizer.id,
        tmdb_movie_id=tmdb_movie_id,
        title=title,
        poster_url=poster_url,
        venue=spec.venue,
        starts_at=datetime.now(UTC) + timedelta(days=spec.days_from_now),
        rows=spec.rows,
        seats_per_row=spec.seats_per_row,
        capacity=spec.rows * spec.seats_per_row,
        price_cents=spec.price_cents,
        status=EventStatus.PUBLISHED,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    overrides_by_position = {(o.row_label, o.seat_number): o for o in spec.overrides}
    demo_qr_token = None

    for row_index in range(spec.rows):
        label = compute_row_label(row_index)
        for seat_number in range(1, spec.seats_per_row + 1):
            seat = Seat(
                event_id=event.id,
                row_label=label,
                seat_number=seat_number,
                status=SeatStatus.AVAILABLE,
            )
            db.add(seat)
            db.flush()

            override = overrides_by_position.get((label, seat_number))
            if override is None:
                continue

            seat.status = override.seat_status
            customer = users_by_email[override.customer_email]
            now = datetime.now(UTC)
            ticket = Ticket(
                event_id=event.id,
                seat_id=seat.id,
                owner_id=customer.id,
                status=override.ticket_status,
                qr_secret="",
                held_at=now
                if override.ticket_status == TicketStatus.HELD
                else now - timedelta(minutes=10),
                expires_at=now + timedelta(minutes=5)
                if override.ticket_status == TicketStatus.HELD
                else None,
                paid_at=now if override.ticket_status == TicketStatus.PAID else None,
            )
            db.add(ticket)
            db.flush()
            seat.current_ticket_id = ticket.id
            token = ticketing.issue(ticket)

            if override.ticket_status == TicketStatus.PAID:
                demo_qr_token = token

    db.commit()
    return event, demo_qr_token


def _find_gate_demo(
    db: Session, spec: EventSpec, organizer: User
) -> tuple[Event, str] | None:
    event = db.execute(
        select(Event).where(
            Event.organizer_id == organizer.id, Event.venue == spec.venue
        )
    ).scalar_one_or_none()
    if event is None:
        return None

    paid_override = next(
        (o for o in spec.overrides if o.ticket_status == TicketStatus.PAID), None
    )
    if paid_override is None:
        return None

    seat = db.execute(
        select(Seat).where(
            Seat.event_id == event.id,
            Seat.row_label == paid_override.row_label,
            Seat.seat_number == paid_override.seat_number,
        )
    ).scalar_one_or_none()
    if seat is None or seat.current_ticket_id is None:
        return None

    ticket = db.get(Ticket, seat.current_ticket_id)
    if ticket is None:
        return None

    return event, ticketing.render_token(ticket)


def _print_summary(
    created_events: list[tuple[EventSpec, Event]], gate_demo: tuple[Event, str] | None
) -> None:
    print()
    print("=== Seed credentials (senha em texto plano, apenas para dev) ===")
    for email, password, role, name in USERS:
        print(f"{role.value:<11}: {email} / {password}  ({name})")
    print("==================================================================")
    for spec, event in created_events:
        print(
            f"Event: {event.title!r} ({event.id}) at {event.venue}, {spec.rows * spec.seats_per_row} seats"
        )
    if gate_demo is not None:
        event, qr_token = gate_demo
        print()
        print(f"Gate demo — event_id: {event.id}")
        print(f"Gate demo — PAID ticket QR token: {qr_token}")


def main() -> None:
    db = SessionLocal()
    try:
        users_by_email = {
            email: _get_or_create_user(db, email, password, role, name)
            for email, password, role, name in USERS
        }

        created_events: list[tuple[EventSpec, Event]] = []

        for spec in EVENT_SPECS:
            organizer = users_by_email[spec.organizer_email]
            existing_event = db.execute(
                select(Event).where(
                    Event.organizer_id == organizer.id, Event.venue == spec.venue
                )
            ).scalar_one_or_none()

            if existing_event is not None:
                print(
                    f"Event already exists at {spec.venue!r} for {spec.organizer_email}, skipping"
                )
                continue

            event, _ = _create_event_with_seats(db, spec, organizer, users_by_email)
            created_events.append((spec, event))

        gate_demo_spec = EVENT_SPECS[0]
        gate_demo = _find_gate_demo(
            db, gate_demo_spec, users_by_email[gate_demo_spec.organizer_email]
        )

        _print_summary(created_events, gate_demo)
    finally:
        db.close()


if __name__ == "__main__":
    main()
