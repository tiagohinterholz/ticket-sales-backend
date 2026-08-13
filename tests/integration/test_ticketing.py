import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import engine
from app.models.event import Event
from app.models.seat import Seat
from app.models.ticket import Ticket, TicketStatus
from app.models.user import Role, User
from app.services import ticketing
from tests.integration.factories import make_event, make_seat, make_ticket, make_user

RaceSessionFactory = sessionmaker(bind=engine)


class TestIssue:
    def test_issue_generates_token_verifiable_by_validate(self, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            status=TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        previous_secret = ticket.qr_secret

        token = ticketing.issue(ticket)
        db_session.commit()

        assert ticket.qr_secret != previous_secret
        assert token.count(".") == 2
        assert ticketing.validate(db_session, token, event.id) == ticketing.GateResult.VALID


class TestValidate:
    def test_validate_tampered_signature_returns_invalid(self, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            status=TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        token = ticketing.issue(ticket)
        db_session.commit()
        payload, signature = token.rsplit(".", 1)
        flipped_char = "0" if signature[-1] != "0" else "1"
        tampered_token = f"{payload}.{signature[:-1]}{flipped_char}"

        result = ticketing.validate(db_session, tampered_token, event.id)

        assert result == ticketing.GateResult.INVALID

    def test_validate_malformed_token_returns_invalid(self, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        event = make_event(db_session, organizer)

        result = ticketing.validate(db_session, "not-a-valid-token", event.id)

        assert result == ticketing.GateResult.INVALID

    def test_validate_well_formed_token_without_matching_ticket_returns_invalid(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            status=TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        token = ticketing.issue(ticket)
        db_session.commit()
        db_session.delete(ticket)
        db_session.commit()

        result = ticketing.validate(db_session, token, event.id)

        assert result == ticketing.GateResult.INVALID

    def test_validate_paid_ticket_correct_event_returns_valid_and_marks_used(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            status=TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        token = ticketing.issue(ticket)
        db_session.commit()

        result = ticketing.validate(db_session, token, event.id)

        assert result == ticketing.GateResult.VALID
        db_session.expire_all()
        refreshed_ticket = db_session.get(Ticket, ticket.id)
        assert refreshed_ticket.status == TicketStatus.USED
        assert refreshed_ticket.used_at is not None

    def test_validate_used_ticket_returns_already_used_without_changing_used_at(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)
        used_at = datetime.now(UTC) - timedelta(minutes=10)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            status=TicketStatus.USED,
            paid_at=datetime.now(UTC) - timedelta(minutes=20),
            used_at=used_at,
        )
        token = ticketing.issue(ticket)
        db_session.commit()

        result = ticketing.validate(db_session, token, event.id)

        assert result == ticketing.GateResult.ALREADY_USED
        db_session.expire_all()
        refreshed_ticket = db_session.get(Ticket, ticket.id)
        assert refreshed_ticket.used_at.replace(tzinfo=UTC) == used_at

    def test_validate_wrong_event_returns_wrong_event(self, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        other_event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            status=TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        token = ticketing.issue(ticket)
        db_session.commit()

        result = ticketing.validate(db_session, token, other_event.id)

        assert result == ticketing.GateResult.WRONG_EVENT

    def test_validate_concurrent_requests_exactly_one_succeeds(self):
        setup_session = RaceSessionFactory()
        organizer = make_user(setup_session, Role.ORGANIZER)
        customer = make_user(setup_session, Role.CUSTOMER)
        event = make_event(setup_session, organizer)
        seat = make_seat(setup_session, event)
        ticket = make_ticket(
            setup_session,
            event,
            seat,
            customer,
            status=TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        token = ticketing.issue(ticket)
        setup_session.commit()

        try:
            barrier = threading.Barrier(2)
            results: dict[str, ticketing.GateResult] = {}

            def _race(name: str) -> None:
                session = RaceSessionFactory()
                try:
                    barrier.wait(timeout=5)
                    results[name] = ticketing.validate(session, token, event.id)
                finally:
                    session.close()

            thread_a = threading.Thread(target=_race, args=("a",))
            thread_b = threading.Thread(target=_race, args=("b",))
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=10)
            thread_b.join(timeout=10)

            outcomes = [results["a"], results["b"]]
            assert outcomes.count(ticketing.GateResult.VALID) == 1
            assert outcomes.count(ticketing.GateResult.ALREADY_USED) == 1

            setup_session.expire_all()
            refreshed_ticket = setup_session.get(Ticket, ticket.id)
            assert refreshed_ticket.status == TicketStatus.USED
        finally:
            setup_session.rollback()
            setup_session.execute(delete(Ticket).where(Ticket.id == ticket.id))
            setup_session.execute(delete(Seat).where(Seat.id == seat.id))
            setup_session.execute(delete(Event).where(Event.id == event.id))
            setup_session.execute(
                delete(User).where(User.id.in_([organizer.id, customer.id]))
            )
            setup_session.commit()
            setup_session.close()
