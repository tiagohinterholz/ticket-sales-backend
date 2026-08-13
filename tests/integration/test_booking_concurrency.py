import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.session import engine
from app.models.event import Event, EventStatus
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.user import Role, User
from app.services import booking

RaceSessionFactory = sessionmaker(bind=engine)


def _make_user(db_session: Session, role: Role, email: str | None = None) -> User:
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


def _make_event(db_session: Session, organizer: User, **overrides) -> Event:
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


def _make_seat(
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


def _make_ticket(
    db_session: Session,
    event: Event,
    seat: Seat,
    owner: User,
    status: TicketStatus,
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


class TestHoldSeat:
    def test_hold_seat_on_available_seat_creates_held_ticket_and_updates_seat_status(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)

        ticket = booking.hold_seat(db_session, event.id, seat.id, customer.id)

        assert ticket.status == TicketStatus.HELD
        assert ticket.owner_id == customer.id
        assert ticket.expires_at is not None
        db_session.expire_all()
        refreshed_seat = db_session.get(Seat, seat.id)
        assert refreshed_seat.status == SeatStatus.HOLD
        assert refreshed_seat.current_ticket_id == ticket.id

    def test_hold_seat_on_hold_seat_raises_seat_unavailable_error(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event, status=SeatStatus.HOLD)

        with pytest.raises(booking.SeatUnavailableError):
            booking.hold_seat(db_session, event.id, seat.id, customer.id)

    def test_hold_seat_on_sold_seat_raises_seat_unavailable_error(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event, status=SeatStatus.SOLD)

        with pytest.raises(booking.SeatUnavailableError):
            booking.hold_seat(db_session, event.id, seat.id, customer.id)

    def test_hold_seat_concurrent_requests_exactly_one_succeeds(self):
        setup_session = RaceSessionFactory()
        organizer = _make_user(setup_session, Role.ORGANIZER)
        customer_a = _make_user(setup_session, Role.CUSTOMER)
        customer_b = _make_user(setup_session, Role.CUSTOMER)
        event = _make_event(setup_session, organizer)
        seat = _make_seat(setup_session, event)

        try:
            barrier = threading.Barrier(2)
            results: dict[str, str] = {}

            def _race(name: str, user_id) -> None:
                session = RaceSessionFactory()
                try:
                    barrier.wait(timeout=5)
                    try:
                        booking.hold_seat(session, event.id, seat.id, user_id)
                        results[name] = "ok"
                    except booking.SeatUnavailableError:
                        results[name] = "error"
                finally:
                    session.close()

            thread_a = threading.Thread(target=_race, args=("a", customer_a.id))
            thread_b = threading.Thread(target=_race, args=("b", customer_b.id))
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=10)
            thread_b.join(timeout=10)

            outcomes = [results["a"], results["b"]]
            assert outcomes.count("ok") == 1
            assert outcomes.count("error") == 1

            setup_session.expire_all()
            refreshed_seat = setup_session.get(Seat, seat.id)
            assert refreshed_seat.status == SeatStatus.HOLD
        finally:
            setup_session.rollback()
            setup_session.execute(
                update(Seat).where(Seat.id == seat.id).values(current_ticket_id=None)
            )
            setup_session.execute(delete(Ticket).where(Ticket.seat_id == seat.id))
            setup_session.execute(delete(Seat).where(Seat.id == seat.id))
            setup_session.execute(delete(Event).where(Event.id == event.id))
            setup_session.execute(
                delete(User).where(
                    User.id.in_([organizer.id, customer_a.id, customer_b.id])
                )
            )
            setup_session.commit()
            setup_session.close()


class TestSweepExpiredHolds:
    def test_sweep_expired_holds_releases_expired_hold_and_returns_count(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event, status=SeatStatus.HOLD)
        expired_ticket = _make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.HELD,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        db_session.execute(
            update(Seat)
            .where(Seat.id == seat.id)
            .values(current_ticket_id=expired_ticket.id)
        )
        db_session.commit()

        released_count = booking.sweep_expired_holds(db_session, event_id=event.id)

        assert released_count == 1
        db_session.expire_all()
        refreshed_ticket = db_session.get(Ticket, expired_ticket.id)
        refreshed_seat = db_session.get(Seat, seat.id)
        assert refreshed_ticket.status == TicketStatus.EXPIRED
        assert refreshed_seat.status == SeatStatus.AVAILABLE
        assert refreshed_seat.current_ticket_id is None

    def test_sweep_expired_holds_does_not_touch_valid_holds(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event, status=SeatStatus.HOLD)
        valid_ticket = _make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.HELD,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        released_count = booking.sweep_expired_holds(db_session, event_id=event.id)

        assert released_count == 0
        db_session.expire_all()
        refreshed_ticket = db_session.get(Ticket, valid_ticket.id)
        refreshed_seat = db_session.get(Seat, seat.id)
        assert refreshed_ticket.status == TicketStatus.HELD
        assert refreshed_seat.status == SeatStatus.HOLD


class TestCancelTicket:
    def test_cancel_ticket_within_window_releases_seat_and_marks_cancelled(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(
            db_session, organizer, starts_at=datetime.now(UTC) + timedelta(hours=5)
        )
        seat = _make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = _make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        cancelled = booking.cancel_ticket(db_session, ticket, customer)

        assert cancelled.status == TicketStatus.CANCELLED
        assert cancelled.cancelled_at is not None
        db_session.expire_all()
        refreshed_seat = db_session.get(Seat, seat.id)
        assert refreshed_seat.status == SeatStatus.AVAILABLE
        assert refreshed_seat.current_ticket_id is None

    def test_cancel_ticket_outside_window_raises_cancel_window_error(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(
            db_session, organizer, starts_at=datetime.now(UTC) + timedelta(minutes=30)
        )
        seat = _make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = _make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        with pytest.raises(booking.CancelWindowError):
            booking.cancel_ticket(db_session, ticket, customer)

    def test_cancel_ticket_on_used_ticket_raises_invalid_ticket_state_error(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(
            db_session, organizer, starts_at=datetime.now(UTC) + timedelta(hours=5)
        )
        seat = _make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = _make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.USED,
            paid_at=datetime.now(UTC),
            used_at=datetime.now(UTC),
        )

        with pytest.raises(booking.InvalidTicketStateError):
            booking.cancel_ticket(db_session, ticket, customer)

    def test_cancel_ticket_on_transferred_ticket_raises_invalid_ticket_state_error(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(
            db_session, organizer, starts_at=datetime.now(UTC) + timedelta(hours=5)
        )
        seat = _make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = _make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.TRANSFERRED,
            paid_at=datetime.now(UTC),
        )

        with pytest.raises(booking.InvalidTicketStateError):
            booking.cancel_ticket(db_session, ticket, customer)
