from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.payment_attempt import PaymentAttempt, PaymentResult
from app.models.seat import SeatStatus
from app.models.ticket import TicketStatus
from app.models.user import Role
from app.services import payment_sim, ticketing
from tests.integration.factories import make_event, make_seat, make_ticket, make_user


class TestAttemptPayment:
    def test_declined_card_keeps_ticket_held_and_records_declined_attempt(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.HOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

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
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.HOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        held_qr_secret = ticket.qr_secret

        outcome = payment_sim.attempt_payment(db_session, ticket.id, "4111111111111234")

        assert outcome.ticket.status == TicketStatus.PAID
        assert outcome.ticket.paid_at is not None
        assert outcome.payment_attempt.result == PaymentResult.APPROVED
        assert outcome.payment_attempt.card_last4 == "1234"
        assert outcome.ticket.qr_secret != held_qr_secret
        assert ticketing.render_token(outcome.ticket).count(".") == 2

    def test_expired_hold_still_flagged_held_raises_hold_expired_error(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.HOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )

        with pytest.raises(payment_sim.HoldExpiredError):
            payment_sim.attempt_payment(db_session, ticket.id, "4111111111111234")

    def test_declined_attempt_allows_retry_within_same_hold(self, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.HOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

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
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.AVAILABLE)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            status=TicketStatus.EXPIRED,
            expires_at=datetime.now(UTC) - timedelta(minutes=10),
        )

        with pytest.raises(payment_sim.HoldExpiredError):
            payment_sim.attempt_payment(db_session, ticket.id, "4111111111111234")
