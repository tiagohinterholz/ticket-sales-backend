import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.event import Event, EventStatus
from app.models.seat import Seat, SeatStatus
from app.models.user import Role, User


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


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


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
    db_session: Session, event: Event, status: SeatStatus = SeatStatus.AVAILABLE
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


class TestHoldSeatEndpoint:
    def test_hold_free_seat_returns_201_with_expires_at(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)

        response = client.post(
            f"/events/{event.id}/seats/{seat.id}/hold",
            headers=_auth_headers(customer),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "HELD"
        assert body["expires_at"] is not None
        assert body["seat_id"] == str(seat.id)

    def test_hold_occupied_seat_returns_409(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event, status=SeatStatus.HOLD)

        response = client.post(
            f"/events/{event.id}/seats/{seat.id}/hold",
            headers=_auth_headers(customer),
        )

        assert response.status_code == 409

    def test_hold_seat_by_organizer_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)

        response = client.post(
            f"/events/{event.id}/seats/{seat.id}/hold",
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 403

    def test_hold_seat_by_gate_staff_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        gate_staff = _make_user(db_session, Role.GATE_STAFF)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)

        response = client.post(
            f"/events/{event.id}/seats/{seat.id}/hold",
            headers=_auth_headers(gate_staff),
        )

        assert response.status_code == 403

    def test_hold_seat_without_auth_returns_401(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)

        response = client.post(f"/events/{event.id}/seats/{seat.id}/hold")

        assert response.status_code == 401
