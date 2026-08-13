import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.event import Event, EventStatus
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
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
    **overrides,
) -> Ticket:
    defaults = {
        "event_id": event.id,
        "seat_id": seat.id,
        "owner_id": owner.id,
        "status": TicketStatus.HELD,
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


class TestPayTicketEndpoint:
    def test_pay_with_approved_card_returns_200_with_paid_ticket(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)
        ticket = _make_ticket(db_session, event, seat, customer)

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
            headers=_auth_headers(customer),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "APPROVED"
        assert body["ticket"]["status"] == "PAID"

    def test_pay_with_declined_card_returns_200_with_declined_status_and_active_hold(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)
        ticket = _make_ticket(db_session, event, seat, customer)

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111110000"},
            headers=_auth_headers(customer),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "DECLINED"
        assert body["ticket"]["status"] == "HELD"
        assert body["ticket"]["expires_at"] is not None

    def test_pay_on_expired_hold_returns_410(
        self, client: TestClient, db_session: Session
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

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
            headers=_auth_headers(customer),
        )

        assert response.status_code == 410

    def test_pay_ticket_owned_by_another_customer_returns_404(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        owner = _make_user(db_session, Role.CUSTOMER)
        other_customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)
        ticket = _make_ticket(db_session, event, seat, owner)

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
            headers=_auth_headers(other_customer),
        )

        assert response.status_code == 404

    def test_pay_by_organizer_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)
        ticket = _make_ticket(db_session, event, seat, customer)

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 403

    def test_pay_without_auth_returns_401(
        self, client: TestClient, db_session: Session
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        customer = _make_user(db_session, Role.CUSTOMER)
        event = _make_event(db_session, organizer)
        seat = _make_seat(db_session, event)
        ticket = _make_ticket(db_session, event, seat, customer)

        response = client.post(
            f"/tickets/{ticket.id}/pay",
            json={"card_number": "4111111111111234"},
        )

        assert response.status_code == 401
