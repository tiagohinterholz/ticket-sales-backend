import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.seat import SeatStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.transfer_invite import TransferInviteStatus
from app.models.user import Role
from tests.integration.factories import (
    auth_headers,
    make_event,
    make_seat,
    make_ticket,
    make_transfer_invite,
    make_user,
)


class TestCreateTransferInvite:
    def test_owner_creates_invite_for_paid_ticket_returns_201_pending(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        response = client.post(
            f"/tickets/{ticket.id}/transfers",
            json={"to_email": "recipient@example.com"},
            headers=auth_headers(owner),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "PENDING"
        assert body["ticket_id"] == str(ticket.id)
        assert body["to_email"] == "recipient@example.com"

    def test_create_invite_for_non_paid_ticket_returns_422(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.HOLD)
        ticket = make_ticket(db_session, event, seat, owner, TicketStatus.HELD)

        response = client.post(
            f"/tickets/{ticket.id}/transfers",
            json={"to_email": "recipient@example.com"},
            headers=auth_headers(owner),
        )

        assert response.status_code == 422

    def test_create_invite_for_ticket_owned_by_another_customer_returns_404(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        stranger = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        response = client.post(
            f"/tickets/{ticket.id}/transfers",
            json={"to_email": "recipient@example.com"},
            headers=auth_headers(stranger),
        )

        assert response.status_code == 404

    def test_create_invite_without_auth_returns_401(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        response = client.post(
            f"/tickets/{ticket.id}/transfers",
            json={"to_email": "recipient@example.com"},
        )

        assert response.status_code == 401

    def test_create_invite_by_gate_staff_returns_403(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        gate_staff = make_user(db_session, Role.GATE_STAFF)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )

        response = client.post(
            f"/tickets/{ticket.id}/transfers",
            json={"to_email": "recipient@example.com"},
            headers=auth_headers(gate_staff),
        )

        assert response.status_code == 403


class TestViewTransferInvite:
    def test_any_authenticated_customer_views_invite_data(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        viewer = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(db_session, ticket, owner)

        response = client.get(
            f"/transfers/{invite.token}", headers=auth_headers(viewer)
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token"] == invite.token
        assert body["ticket_id"] == str(ticket.id)
        assert body["status"] == "PENDING"

    def test_view_invite_without_auth_returns_401(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(db_session, ticket, owner)

        response = client.get(f"/transfers/{invite.token}")

        assert response.status_code == 401

    def test_view_nonexistent_token_returns_404(self, client: TestClient, db_session: Session):
        customer = make_user(db_session, Role.CUSTOMER)

        response = client.get(
            f"/transfers/{uuid.uuid4().hex}", headers=auth_headers(customer)
        )

        assert response.status_code == 404


class TestAcceptTransferInvite:
    def test_full_happy_path_create_view_accept_ticket_appears_for_new_owner(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER, email="recipient@example.com")
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        db_session.refresh(seat)
        seat.current_ticket_id = ticket.id
        db_session.commit()

        create_response = client.post(
            f"/tickets/{ticket.id}/transfers",
            json={"to_email": "recipient@example.com"},
            headers=auth_headers(owner),
        )
        token = create_response.json()["token"]

        view_response = client.get(
            f"/transfers/{token}", headers=auth_headers(recipient)
        )
        assert view_response.status_code == 200

        accept_response = client.post(
            f"/transfers/{token}/accept", headers=auth_headers(recipient)
        )

        assert accept_response.status_code == 200
        body = accept_response.json()
        assert body["owner_id"] == str(recipient.id)
        assert body["status"] == "PAID"

        recipient_tickets = client.get(
            "/tickets", headers=auth_headers(recipient)
        ).json()
        assert body["id"] in [t["id"] for t in recipient_tickets]

        owner_tickets = client.get("/tickets", headers=auth_headers(owner)).json()
        original_ticket = next(t for t in owner_tickets if t["id"] == str(ticket.id))
        assert original_ticket["status"] == "TRANSFERRED"

    def test_accept_without_auth_returns_401(self, client: TestClient, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(db_session, ticket, owner)

        response = client.post(f"/transfers/{invite.token}/accept")

        assert response.status_code == 401

    def test_accept_nonexistent_token_returns_404(
        self, client: TestClient, db_session: Session
    ):
        customer = make_user(db_session, Role.CUSTOMER)

        response = client.post(
            f"/transfers/{uuid.uuid4().hex}/accept", headers=auth_headers(customer)
        )

        assert response.status_code == 404

    def test_accept_expired_invite_returns_410(self, client: TestClient, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(
            db_session, ticket, owner,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )

        response = client.post(
            f"/transfers/{invite.token}/accept", headers=auth_headers(recipient)
        )

        assert response.status_code == 410


class TestDeclineTransferInvite:
    def test_decline_returns_200_and_original_ticket_stays_paid(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(db_session, ticket, owner)

        response = client.post(
            f"/transfers/{invite.token}/decline", headers=auth_headers(recipient)
        )

        assert response.status_code == 200
        assert response.json()["status"] == "DECLINED"
        unchanged_ticket = db_session.get(Ticket, ticket.id)
        assert unchanged_ticket.status == TicketStatus.PAID

    def test_decline_without_auth_returns_401(self, client: TestClient, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(db_session, ticket, owner)

        response = client.post(f"/transfers/{invite.token}/decline")

        assert response.status_code == 401

    def test_decline_already_accepted_invite_returns_410(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(
            db_session, ticket, owner, status=TransferInviteStatus.ACCEPTED
        )

        response = client.post(
            f"/transfers/{invite.token}/decline", headers=auth_headers(recipient)
        )

        assert response.status_code == 410


class TestCancelTransferInvite:
    def test_owner_cancels_pending_invite_and_later_accept_returns_410(
        self, client: TestClient, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(db_session, ticket, owner)

        cancel_response = client.post(
            f"/transfers/{invite.token}/cancel", headers=auth_headers(owner)
        )
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "CANCELLED"

        accept_response = client.post(
            f"/transfers/{invite.token}/accept", headers=auth_headers(recipient)
        )
        assert accept_response.status_code == 410

        unchanged_ticket = db_session.get(Ticket, ticket.id)
        assert unchanged_ticket.status == TicketStatus.PAID

    def test_cancel_by_non_owner_returns_403(self, client: TestClient, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        stranger = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(db_session, ticket, owner)

        response = client.post(
            f"/transfers/{invite.token}/cancel", headers=auth_headers(stranger)
        )

        assert response.status_code == 403
        unchanged_invite = db_session.get(type(invite), invite.id)
        assert unchanged_invite.status == TransferInviteStatus.PENDING

    def test_cancel_without_auth_returns_401(self, client: TestClient, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(
            db_session, event, seat, owner, TicketStatus.PAID,
            paid_at=datetime.now(UTC),
        )
        invite = make_transfer_invite(db_session, ticket, owner)

        response = client.post(f"/transfers/{invite.token}/cancel")

        assert response.status_code == 401

    def test_cancel_nonexistent_token_returns_404(
        self, client: TestClient, db_session: Session
    ):
        customer = make_user(db_session, Role.CUSTOMER)

        response = client.post(
            f"/transfers/{uuid.uuid4().hex}/cancel", headers=auth_headers(customer)
        )

        assert response.status_code == 404
