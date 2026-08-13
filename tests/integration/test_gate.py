from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.seat import SeatStatus
from app.models.ticket import TicketStatus
from app.models.user import Role
from app.services import ticketing
from tests.integration.factories import (
    auth_headers,
    make_event,
    make_seat,
    make_ticket,
    make_user,
)


class TestValidateEndpoint:
    def test_validate_paid_ticket_correct_event_returns_valid_with_seat_and_customer(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        gate_staff = make_user(db_session, Role.GATE_STAFF)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD, row_label="B", seat_number=7)
        ticket = make_ticket(
            db_session, event, seat, customer, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        token = ticketing.issue(ticket)
        db_session.commit()

        response = client.post(
            "/gate/validate",
            json={"event_id": str(event.id), "token": token},
            headers=auth_headers(gate_staff),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["result"] == "VALID"
        assert body["ticket_id"] == str(ticket.id)
        assert body["seat"]["row_label"] == "B"
        assert body["seat"]["seat_number"] == 7
        assert body["customer_name"] == customer.name
        assert body["customer_email"] == customer.email

    def test_validate_already_used_ticket_returns_already_used(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        gate_staff = make_user(db_session, Role.GATE_STAFF)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, customer, TicketStatus.USED,
            paid_at=datetime.now(UTC) - timedelta(minutes=10),
            used_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        token = ticketing.issue(ticket)
        db_session.commit()

        response = client.post(
            "/gate/validate",
            json={"event_id": str(event.id), "token": token},
            headers=auth_headers(gate_staff),
        )

        assert response.status_code == 200
        assert response.json()["result"] == "ALREADY_USED"

    def test_validate_wrong_event_returns_wrong_event(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        gate_staff = make_user(db_session, Role.GATE_STAFF)
        customer = make_user(db_session, Role.CUSTOMER)
        ticket_event = make_event(db_session, organizer)
        gate_event = make_event(db_session, organizer)
        seat = make_seat(db_session, ticket_event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, ticket_event, seat, customer, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        token = ticketing.issue(ticket)
        db_session.commit()

        response = client.post(
            "/gate/validate",
            json={"event_id": str(gate_event.id), "token": token},
            headers=auth_headers(gate_staff),
        )

        assert response.status_code == 200
        assert response.json()["result"] == "WRONG_EVENT"

    def test_validate_malformed_token_returns_invalid(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        gate_staff = make_user(db_session, Role.GATE_STAFF)
        event = make_event(db_session, organizer)

        response = client.post(
            "/gate/validate",
            json={"event_id": str(event.id), "token": "totally-bogus-code"},
            headers=auth_headers(gate_staff),
        )

        assert response.status_code == 200
        assert response.json()["result"] == "INVALID"

    def test_manual_code_yields_same_result_as_token_for_the_same_ticket(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        gate_staff = make_user(db_session, Role.GATE_STAFF)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, customer, TicketStatus.USED,
            paid_at=datetime.now(UTC) - timedelta(minutes=10),
            used_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        token = ticketing.issue(ticket)
        db_session.commit()

        via_token = client.post(
            "/gate/validate",
            json={"event_id": str(event.id), "token": token},
            headers=auth_headers(gate_staff),
        )
        via_manual_code = client.post(
            "/gate/validate",
            json={"event_id": str(event.id), "manual_code": token},
            headers=auth_headers(gate_staff),
        )

        assert via_token.status_code == via_manual_code.status_code == 200
        assert via_token.json() == via_manual_code.json() == {
            "result": "ALREADY_USED",
            "ticket_id": None,
            "seat": None,
            "customer_name": None,
            "customer_email": None,
        }

    def test_validate_by_customer_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)

        response = client.post(
            "/gate/validate",
            json={"event_id": str(event.id), "token": "irrelevant"},
            headers=auth_headers(customer),
        )

        assert response.status_code == 403

    def test_validate_by_organizer_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        event = make_event(db_session, organizer)

        response = client.post(
            "/gate/validate",
            json={"event_id": str(event.id), "token": "irrelevant"},
            headers=auth_headers(organizer),
        )

        assert response.status_code == 403

    def test_validate_without_token_or_manual_code_returns_422(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        gate_staff = make_user(db_session, Role.GATE_STAFF)
        event = make_event(db_session, organizer)

        response = client.post(
            "/gate/validate",
            json={"event_id": str(event.id)},
            headers=auth_headers(gate_staff),
        )

        assert response.status_code == 422

    def test_validate_without_auth_returns_401(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        event = make_event(db_session, organizer)

        response = client.post(
            "/gate/validate",
            json={"event_id": str(event.id), "token": "irrelevant"},
        )

        assert response.status_code == 401
