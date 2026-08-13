from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.seat import SeatStatus
from app.models.user import Role
from tests.integration.factories import (
    auth_headers,
    make_event,
    make_seat,
    make_ticket,
    make_user,
)


class TestPayTicketEndpoint:
    def test_pay_with_approved_card_returns_200_with_paid_ticket(
        self, client: TestClient, db_session: Session
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

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
            headers=auth_headers(customer),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "APPROVED"
        assert body["ticket"]["status"] == "PAID"

    def test_pay_with_declined_card_returns_200_with_declined_status_and_active_hold(
        self, client: TestClient, db_session: Session
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

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111110000"},
            headers=auth_headers(customer),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "DECLINED"
        assert body["ticket"]["status"] == "HELD"
        assert body["ticket"]["expires_at"] is not None

    def test_pay_on_expired_hold_returns_410(
        self, client: TestClient, db_session: Session
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

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
            headers=auth_headers(customer),
        )

        assert response.status_code == 410

    def test_pay_ticket_owned_by_another_customer_returns_404(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        other_customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.HOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            owner,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
            headers=auth_headers(other_customer),
        )

        assert response.status_code == 404

    def test_pay_by_organizer_returns_403(
        self, client: TestClient, db_session: Session
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

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
            headers=auth_headers(organizer),
        )

        assert response.status_code == 403

    def test_pay_without_auth_returns_401(
        self, client: TestClient, db_session: Session
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

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
        )

        assert response.status_code == 401
