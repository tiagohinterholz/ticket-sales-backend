from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fake_email_log import FakeEmailLog
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.transfer_invite import TransferInviteStatus
from app.models.user import Role
from app.services import transfer
from tests.integration.factories import (
    make_event,
    make_seat,
    make_ticket,
    make_transfer_invite,
    make_user,
)


class TestCreateInvite:
    def test_non_paid_ticket_raises_invalid_ticket_state(self, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.HOLD)
        ticket = make_ticket(db_session, event, seat, owner, status=TicketStatus.HELD)

        with pytest.raises(transfer.InvalidTicketStateError):
            transfer.create_invite(
                db_session, ticket.id, owner.id, "someone@example.com"
            )

    def test_email_matching_existing_customer_resolves_to_user_id_no_fake_email(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER, email="recipient@example.com")
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(db_session, event, seat, owner, status=TicketStatus.PAID)

        invite = transfer.create_invite(
            db_session, ticket.id, owner.id, "recipient@example.com"
        )

        assert invite.status == TransferInviteStatus.PENDING
        assert invite.to_user_id == recipient.id
        logged = db_session.execute(
            select(FakeEmailLog).where(FakeEmailLog.to_email == "recipient@example.com")
        ).scalar_one_or_none()
        assert logged is None

    def test_email_without_account_logs_fake_email_and_still_creates_pending_invite(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(db_session, event, seat, owner, status=TicketStatus.PAID)

        invite = transfer.create_invite(
            db_session, ticket.id, owner.id, "unknown@example.com"
        )

        assert invite.status == TransferInviteStatus.PENDING
        assert invite.to_user_id is None
        logged = db_session.execute(
            select(FakeEmailLog).where(FakeEmailLog.to_email == "unknown@example.com")
        ).scalar_one_or_none()
        assert logged is not None


class TestAccept:
    def test_accept_transfers_ownership_atomically_with_new_qr_and_updates_seat(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(db_session, event, seat, owner, status=TicketStatus.PAID)
        db_session.refresh(seat)
        seat.current_ticket_id = ticket.id
        db_session.commit()
        original_qr_secret = ticket.qr_secret
        invite = make_transfer_invite(
            db_session, ticket, owner, to_user_id=recipient.id
        )

        new_ticket = transfer.accept(db_session, invite.token, recipient.id)

        assert new_ticket.owner_id == recipient.id
        assert new_ticket.status == TicketStatus.PAID
        assert new_ticket.event_id == ticket.event_id
        assert new_ticket.seat_id == ticket.seat_id
        assert new_ticket.qr_secret != original_qr_secret

        original_ticket = db_session.get(Ticket, ticket.id)
        assert original_ticket.status == TicketStatus.TRANSFERRED

        refreshed_seat = db_session.get(Seat, seat.id)
        assert refreshed_seat.current_ticket_id == new_ticket.id

        refreshed_invite = db_session.get(type(invite), invite.id)
        assert refreshed_invite.status == TransferInviteStatus.ACCEPTED

        old_owner_active_tickets = (
            db_session.execute(
                select(Ticket).where(
                    Ticket.owner_id == owner.id, Ticket.status == TicketStatus.PAID
                )
            )
            .scalars()
            .all()
        )
        assert ticket.id not in [t.id for t in old_owner_active_tickets]

    def test_expired_invite_cannot_be_accepted_and_ticket_stays_paid(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(db_session, event, seat, owner, status=TicketStatus.PAID)
        invite = make_transfer_invite(
            db_session,
            ticket,
            owner,
            to_user_id=recipient.id,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )

        with pytest.raises(transfer.TransferInviteExpiredError):
            transfer.accept(db_session, invite.token, recipient.id)

        unchanged_ticket = db_session.get(Ticket, ticket.id)
        assert unchanged_ticket.status == TicketStatus.PAID


class TestDecline:
    def test_decline_keeps_ticket_paid_and_invalidates_the_link(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(db_session, event, seat, owner, status=TicketStatus.PAID)
        invite = make_transfer_invite(
            db_session, ticket, owner, to_user_id=recipient.id
        )

        declined_invite = transfer.decline(db_session, invite.token)

        assert declined_invite.status == TransferInviteStatus.DECLINED
        unchanged_ticket = db_session.get(Ticket, ticket.id)
        assert unchanged_ticket.status == TicketStatus.PAID

        with pytest.raises(transfer.TransferInviteNotPendingError):
            transfer.accept(db_session, invite.token, recipient.id)


class TestCancelInvite:
    def test_owner_cancels_pending_invite_ticket_stays_paid_and_link_invalidated(
        self, db_session: Session
    ):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        recipient = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(db_session, event, seat, owner, status=TicketStatus.PAID)
        invite = make_transfer_invite(
            db_session, ticket, owner, to_user_id=recipient.id
        )

        cancelled_invite = transfer.cancel_invite(db_session, invite.token, owner.id)

        assert cancelled_invite.status == TransferInviteStatus.CANCELLED
        unchanged_ticket = db_session.get(Ticket, ticket.id)
        assert unchanged_ticket.status == TicketStatus.PAID

        with pytest.raises(transfer.TransferInviteNotPendingError):
            transfer.accept(db_session, invite.token, recipient.id)

    def test_non_owner_cannot_cancel_invite(self, db_session: Session):
        organizer = make_user(db_session, Role.ORGANIZER)
        owner = make_user(db_session, Role.CUSTOMER)
        stranger = make_user(db_session, Role.CUSTOMER)
        event = make_event(db_session, organizer)
        seat = make_seat(db_session, event, status=SeatStatus.SOLD)
        ticket = make_ticket(db_session, event, seat, owner, status=TicketStatus.PAID)
        invite = make_transfer_invite(db_session, ticket, owner)

        with pytest.raises(transfer.TransferInviteForbiddenError):
            transfer.cancel_invite(db_session, invite.token, stranger.id)

        unchanged_invite = db_session.get(type(invite), invite.id)
        assert unchanged_invite.status == TransferInviteStatus.PENDING
