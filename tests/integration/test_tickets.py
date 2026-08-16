import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.seat import Seat, SeatStatus
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


class TestListMyTickets:
    def test_list_returns_only_own_tickets_across_statuses(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        other_customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)

        paid_seat = make_seat(db_session, event, status=SeatStatus.SOLD, seat_number=1)
        used_seat = make_seat(db_session, event, status=SeatStatus.SOLD, seat_number=2)
        cancelled_seat = make_seat(
            db_session, event, status=SeatStatus.AVAILABLE, seat_number=3
        )
        transferred_seat = make_seat(
            db_session, event, status=SeatStatus.SOLD, seat_number=4
        )
        other_seat = make_seat(db_session, event, status=SeatStatus.SOLD, seat_number=5)

        paid_ticket = make_ticket(
            db_session, event, paid_seat, customer, TicketStatus.PAID
        )
        used_ticket = make_ticket(
            db_session, event, used_seat, customer, TicketStatus.USED
        )
        cancelled_ticket = make_ticket(
            db_session, event, cancelled_seat, customer, TicketStatus.CANCELLED
        )
        transferred_ticket = make_ticket(
            db_session, event, transferred_seat, customer, TicketStatus.TRANSFERRED
        )
        make_ticket(db_session, event, other_seat, other_customer, TicketStatus.PAID)

        response = client.get("/tickets", headers=auth_headers(customer))

        assert response.status_code == 200
        returned_ids = {item["id"] for item in response.json()}
        assert returned_ids == {
            str(paid_ticket.id),
            str(used_ticket.id),
            str(cancelled_ticket.id),
            str(transferred_ticket.id),
        }

    def test_list_without_auth_returns_401(self, client: TestClient):
        response = client.get("/tickets")

        assert response.status_code == 401

    def test_list_by_organizer_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)

        response = client.get("/tickets", headers=auth_headers(organizer))

        assert response.status_code == 403


class TestGetTicketDetail:
    def test_detail_of_paid_ticket_returns_working_qr_token(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        response = client.get(f"/tickets/{ticket.id}", headers=auth_headers(customer))

        assert response.status_code == 200
        body = response.json()
        assert body["qr_token"] is not None
        assert ticketing.validate(db_session, body["qr_token"], event.id) == (
            ticketing.GateResult.VALID
        )

    def test_detail_viewed_twice_returns_the_same_qr_token(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        first_response = client.get(
            f"/tickets/{ticket.id}", headers=auth_headers(customer)
        )
        second_response = client.get(
            f"/tickets/{ticket.id}", headers=auth_headers(customer)
        )

        assert first_response.json()["qr_token"] == second_response.json()["qr_token"]

    def test_detail_of_used_ticket_returns_null_qr_token(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.USED,
            paid_at=datetime.now(UTC),
            used_at=datetime.now(UTC),
        )

        response = client.get(f"/tickets/{ticket.id}", headers=auth_headers(customer))

        assert response.status_code == 200
        assert response.json()["qr_token"] is None

    def test_detail_of_cancelled_ticket_returns_null_qr_token(
        self, client: TestClient, db_session: Session
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
            TicketStatus.CANCELLED,
            paid_at=datetime.now(UTC),
            cancelled_at=datetime.now(UTC),
        )

        response = client.get(f"/tickets/{ticket.id}", headers=auth_headers(customer))

        assert response.status_code == 200
        assert response.json()["qr_token"] is None

    def test_detail_of_transferred_ticket_returns_null_qr_token(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.TRANSFERRED,
            paid_at=datetime.now(UTC),
        )

        response = client.get(f"/tickets/{ticket.id}", headers=auth_headers(customer))

        assert response.status_code == 200
        assert response.json()["qr_token"] is None

    def test_detail_of_ticket_owned_by_another_customer_returns_404(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        other_customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            owner,
            TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        response = client.get(
            f"/tickets/{ticket.id}", headers=auth_headers(other_customer)
        )

        assert response.status_code == 404

    def test_detail_of_nonexistent_ticket_returns_404(
        self, client: TestClient, db_session: Session
    ):
        customer = make_user(db_session, Role.CUSTOMER)

        response = client.get(
            f"/tickets/{uuid.uuid4()}", headers=auth_headers(customer)
        )

        assert response.status_code == 404

    def test_detail_without_auth_returns_401(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        response = client.get(f"/tickets/{ticket.id}")

        assert response.status_code == 401


class TestCancelTicketEndpoint:
    def test_cancel_more_than_2h_before_event_returns_200_cancelled_and_frees_seat(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(
            db_session, organizer, starts_at=datetime.now(UTC) + timedelta(hours=5)
        )
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        response = client.post(
            f"/tickets/{ticket.id}/cancel", headers=auth_headers(customer)
        )

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"
        db_session.expire_all()
        refreshed_seat = db_session.get(Seat, seat.id)
        assert refreshed_seat.status == SeatStatus.AVAILABLE

    def test_cancel_less_than_2h_before_event_returns_422_with_clear_message(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(
            db_session, organizer, starts_at=datetime.now(UTC) + timedelta(minutes=30)
        )
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        response = client.post(
            f"/tickets/{ticket.id}/cancel", headers=auth_headers(customer)
        )

        assert response.status_code == 422
        assert "2 hours" in response.json()["detail"]

    def test_cancel_used_ticket_returns_422(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(
            db_session, organizer, starts_at=datetime.now(UTC) + timedelta(hours=5)
        )
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.USED,
            paid_at=datetime.now(UTC),
            used_at=datetime.now(UTC),
        )

        response = client.post(
            f"/tickets/{ticket.id}/cancel", headers=auth_headers(customer)
        )

        assert response.status_code == 422

    def test_cancel_transferred_ticket_returns_422(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(
            db_session, organizer, starts_at=datetime.now(UTC) + timedelta(hours=5)
        )
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session,
            event,
            seat,
            customer,
            TicketStatus.TRANSFERRED,
            paid_at=datetime.now(UTC),
        )

        response = client.post(
            f"/tickets/{ticket.id}/cancel", headers=auth_headers(customer)
        )

        assert response.status_code == 422
