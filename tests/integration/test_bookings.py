from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.seat import SeatStatus
from app.models.user import Role
from tests.integration.factories import auth_headers, make_event, make_seat, make_user


class TestHoldSeatEndpoint:
    def test_hold_free_seat_returns_201_with_expires_at(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)

        response = client.post(
            f"/events/{event.id}/seats/{seat.id}/hold",
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "HELD"
        assert body["expires_at"] is not None
        assert body["seat_id"] == str(seat.id)

    def test_hold_occupied_seat_returns_409(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        customer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.HOLD)

        response = client.post(
            f"/events/{event.id}/seats/{seat.id}/hold",
            headers=auth_headers(customer),
        )

        assert response.status_code == 409

    def test_hold_seat_by_organizer_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)

        response = client.post(
            f"/events/{event.id}/seats/{seat.id}/hold",
            headers=auth_headers(organizer),
        )

        assert response.status_code == 403

    def test_hold_seat_by_gate_staff_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        gate_staff = make_user(db_session, Role.GATE_STAFF)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)

        response = client.post(
            f"/events/{event.id}/seats/{seat.id}/hold",
            headers=auth_headers(gate_staff),
        )

        assert response.status_code == 403

    def test_hold_seat_without_auth_returns_401(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event)

        response = client.post(f"/events/{event.id}/seats/{seat.id}/hold")

        assert response.status_code == 401
