import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.seat import SeatStatus
from app.models.ticket import TicketStatus
from app.models.user import Role
from tests.integration.factories import (
    auth_headers,
    make_event,
    make_seat,
    make_ticket,
    make_user,
)


class TestListOrganizerEvents:
    def test_list_events_returns_only_authenticated_organizer_events_with_percent_sold(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        other_organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)

        own_event = make_event(db_session, organizer, capacity=2)
        seat_a = make_seat(db_session, own_event, row_label="A", seat_number=1)
        make_seat(db_session, own_event, row_label="A", seat_number=2)
        make_ticket(db_session, own_event, seat_a, customer, status=TicketStatus.PAID)

        make_event(db_session, other_organizer, capacity=5)

        response = client.get("/organizer/events", headers=auth_headers(organizer))

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == str(own_event.id)
        assert body[0]["percent_sold"] == 0.5

    def test_list_events_percent_sold_only_counts_paid_and_used_tickets(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer, capacity=4)
        seat_paid = make_seat(db_session, event, row_label="A", seat_number=1)
        seat_used = make_seat(db_session, event, row_label="A", seat_number=2)
        seat_held = make_seat(db_session, event, row_label="A", seat_number=3)
        seat_cancelled = make_seat(db_session, event, row_label="A", seat_number=4)
        make_ticket(db_session, event, seat_paid, customer, status=TicketStatus.PAID)
        make_ticket(db_session, event, seat_used, customer, status=TicketStatus.USED)
        make_ticket(db_session, event, seat_held, customer, status=TicketStatus.HELD)
        make_ticket(
            db_session, event, seat_cancelled, customer, status=TicketStatus.CANCELLED
        )

        response = client.get("/organizer/events", headers=auth_headers(organizer))

        assert response.status_code == 200
        body = response.json()
        assert body[0]["percent_sold"] == 0.5

    def test_list_events_by_customer_returns_403(
        self, client: TestClient, db_session: Session
    ):
        customer = make_user(db_session, Role.CUSTOMER)

        response = client.get("/organizer/events", headers=auth_headers(customer))

        assert response.status_code == 403

    def test_list_events_without_auth_returns_401(self, client: TestClient):
        response = client.get("/organizer/events")

        assert response.status_code == 401


class TestOrganizerEventSeatMap:
    def test_get_event_seats_reflects_available_hold_and_sold_status(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer, capacity=3)
        available_seat = make_seat(db_session, event, row_label="A", seat_number=1)
        hold_seat = make_seat(
            db_session, event, row_label="A", seat_number=2, status=SeatStatus.HOLD
        )
        sold_seat = make_seat(
            db_session, event, row_label="A", seat_number=3, status=SeatStatus.SOLD
        )
        make_ticket(db_session, event, hold_seat, customer, status=TicketStatus.HELD)
        make_ticket(db_session, event, sold_seat, customer, status=TicketStatus.PAID)

        response = client.get(
            f"/organizer/events/{event.id}/seats", headers=auth_headers(organizer)
        )

        assert response.status_code == 200
        body = response.json()
        statuses = {seat["id"]: seat["status"] for seat in body["seats"]}
        assert statuses[str(available_seat.id)] == "AVAILABLE"
        assert statuses[str(hold_seat.id)] == "HOLD"
        assert statuses[str(sold_seat.id)] == "SOLD"

    def test_get_event_seats_shows_available_after_ticket_cancellation(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer, capacity=1)
        seat = make_seat(db_session, event, status=SeatStatus.AVAILABLE)
        make_ticket(
            db_session,
            event,
            seat,
            customer,
            status=TicketStatus.CANCELLED,
            cancelled_at=datetime.now(UTC),
        )

        response = client.get(
            f"/organizer/events/{event.id}/seats", headers=auth_headers(organizer)
        )

        assert response.status_code == 200
        body = response.json()
        assert body["seats"][0]["status"] == "AVAILABLE"

    def test_get_event_seats_for_other_organizer_event_returns_404(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        other_organizer = make_user(db_session, Role.ORGANIZER)
        other_event = make_event(db_session, other_organizer)

        response = client.get(
            f"/organizer/events/{other_event.id}/seats",
            headers=auth_headers(organizer),
        )

        assert response.status_code == 404

    def test_get_event_seats_for_nonexistent_event_returns_404(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)

        response = client.get(
            f"/organizer/events/{uuid.uuid4()}/seats",
            headers=auth_headers(organizer),
        )

        assert response.status_code == 404

    def test_get_event_seats_by_customer_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)

        response = client.get(
            f"/organizer/events/{event.id}/seats", headers=auth_headers(customer)
        )

        assert response.status_code == 403
