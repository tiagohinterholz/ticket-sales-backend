import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutils import as_utc
from app.models.fake_email_log import FakeEmailLog
from app.models.seat import Seat
from app.models.ticket import Ticket, TicketStatus
from app.models.transfer_invite import TransferInvite, TransferInviteStatus
from app.models.user import Role, User
from app.services import ticketing


class InvalidTicketStateError(Exception):
    pass


class TransferInviteNotFoundError(Exception):
    pass


class TransferInviteNotPendingError(Exception):
    pass


class TransferInviteExpiredError(Exception):
    pass


class TransferInviteForbiddenError(Exception):
    pass


def _get_invite_by_token(db: Session, token: str) -> TransferInvite:
    invite = db.execute(
        select(TransferInvite).where(TransferInvite.token == token)
    ).scalar_one_or_none()
    if invite is None:
        raise TransferInviteNotFoundError("Transfer invite not found")
    return invite


def create_invite(
    db: Session, ticket_id: UUID, from_user_id: UUID, to_email: str
) -> TransferInvite:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.status != TicketStatus.PAID:
        raise InvalidTicketStateError("Only a PAID ticket can be transferred")

    to_user = db.execute(
        select(User).where(User.email == to_email, User.role == Role.CUSTOMER)
    ).scalar_one_or_none()

    if to_user is None:
        db.add(
            FakeEmailLog(
                to_email=to_email,
                subject="Você recebeu um convite de transferência de ingresso",
                body=f"Acesse o convite para o ingresso {ticket.id} e crie uma conta para aceitar.",
            )
        )

    invite = TransferInvite(
        ticket_id=ticket.id,
        from_user_id=from_user_id,
        to_email=to_email,
        to_user_id=to_user.id if to_user is not None else None,
        token=secrets.token_urlsafe(32),
        status=TransferInviteStatus.PENDING,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.TRANSFER_EXPIRY_HOURS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def accept(db: Session, token: str, accepting_user_id: UUID) -> Ticket:
    invite = _get_invite_by_token(db, token)
    if invite.status != TransferInviteStatus.PENDING:
        raise TransferInviteNotPendingError("Transfer invite is no longer pending")
    if as_utc(invite.expires_at) < datetime.now(UTC):
        raise TransferInviteExpiredError("Transfer invite has expired")

    original_ticket = db.get(Ticket, invite.ticket_id)
    if original_ticket is None or original_ticket.status != TicketStatus.PAID:
        raise InvalidTicketStateError("Only a PAID ticket can be transferred")

    now = datetime.now(UTC)
    original_ticket.status = TicketStatus.TRANSFERRED

    new_ticket = Ticket(
        event_id=original_ticket.event_id,
        seat_id=original_ticket.seat_id,
        owner_id=accepting_user_id,
        status=TicketStatus.PAID,
        qr_secret=secrets.token_hex(32),
        held_at=now,
        paid_at=now,
    )
    db.add(new_ticket)
    db.flush()
    ticketing.issue(new_ticket)

    seat = db.get(Seat, original_ticket.seat_id)
    seat.current_ticket_id = new_ticket.id

    invite.status = TransferInviteStatus.ACCEPTED

    db.commit()
    db.refresh(new_ticket)
    return new_ticket


def decline(db: Session, token: str) -> TransferInvite:
    invite = _get_invite_by_token(db, token)
    if invite.status != TransferInviteStatus.PENDING:
        raise TransferInviteNotPendingError("Transfer invite is no longer pending")

    invite.status = TransferInviteStatus.DECLINED
    db.commit()
    db.refresh(invite)
    return invite


def cancel_invite(db: Session, token: str, owner_id: UUID) -> TransferInvite:
    invite = _get_invite_by_token(db, token)
    if invite.from_user_id != owner_id:
        raise TransferInviteForbiddenError("Only the sender can cancel this invite")
    if invite.status != TransferInviteStatus.PENDING:
        raise TransferInviteNotPendingError("Transfer invite is no longer pending")

    invite.status = TransferInviteStatus.CANCELLED
    db.commit()
    db.refresh(invite)
    return invite
