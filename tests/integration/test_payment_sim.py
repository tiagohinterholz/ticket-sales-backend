import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.event import Event, EventStatus
from app.models.payment_attempt import PaymentAttempt, PaymentResult
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.user import Role, User
from app.services import payment_sim


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


def _make_event(db_session: Session, organizer: User) -> Event:
    event = Event(
        organizer_id=organizer.id,
        tmdb_movie_id=uuid.uuid4().int % 1_000_000,
        title=f"Movie {uuid.uuid4()}",
        poster_url=None,
        venue="Test Venue",
        starts_at=datetime.now(UTC) + timedelta(days=7),
        rows=1,
        seats_per_row=1,
        capacity=1,
        price_cents=1000,
        status=EventStatus.PUBLISHED,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


def _make_seat(
    db_session: Session, event: Event, status: SeatStatus = SeatStatus.HOLD
) -> Seat:
    seat = Seat(
        event_id=event.id,
        row_label="A",
        seat_number=1,
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
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
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


class TestAttemptPayment:
    def test_declined_card_keeps_ticket_held_and_records_declined_attempt(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)
        ticket = _make_ticket(db_session, event, seat, customer)

        outcome = payment_sim.attempt_payment(db_session, ticket.id, "4111111111110000")

        assert outcome.ticket.status == TicketStatus.HELD
        assert outcome.ticket.paid_at is None
        assert outcome.payment_attempt.result == PaymentResult.DECLINED
        assert outcome.payment_attempt.card_last4 == "0000"
        stored = db_session.get(PaymentAttempt, outcome.payment_attempt.id)
        assert stored.result == PaymentResult.DECLINED

    def test_approved_card_marks_ticket_paid_and_records_approved_attempt(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)
        ticket = _make_ticket(db_session, event, seat, customer)

        outcome = payment_sim.attempt_payment(db_session, ticket.id, "4111111111111234")

        assert outcome.ticket.status == TicketStatus.PAID
        assert outcome.ticket.paid_at is not None
        assert outcome.payment_attempt.result == PaymentResult.APPROVED
        assert outcome.payment_attempt.card_last4 == "1234"

    def test_expired_hold_still_flagged_held_raises_hold_expired_error(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)
        ticket = _make_ticket(
            db_session,
            event,
            seat,
            customer,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )

        with pytest.raises(payment_sim.HoldExpiredError):
            payment_sim.attempt_payment(db_session, ticket.id, "4111111111111234")

    def test_declined_attempt_allows_retry_within_same_hold(self, db_session: Session):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)
        ticket = _make_ticket(db_session, event, seat, customer)

        declined_outcome = payment_sim.attempt_payment(
            db_session, ticket.id, "4111111111110000"
        )
        assert declined_outcome.ticket.status == TicketStatus.HELD

        approved_outcome = payment_sim.attempt_payment(
            db_session, ticket.id, "4111111111111234"
        )

        assert approved_outcome.ticket.status == TicketStatus.PAID
        assert approved_outcome.payment_attempt.result == PaymentResult.APPROVED

    def test_ticket_already_swept_to_expired_raises_hold_expired_error(
        self, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event, status=SeatStatus.AVAILABLE)
        ticket = _make_ticket(
            db_session,
            event,
            seat,
            customer,
            status=TicketStatus.EXPIRED,
            expires_at=datetime.now(UTC) - timedelta(minutes=10),
        )

        with pytest.raises(payment_sim.HoldExpiredError):
            payment_sim.attempt_payment(db_session, ticket.id, "4111111111111234")

