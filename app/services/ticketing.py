import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ticket import Ticket, TicketStatus


class GateResult(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    ALREADY_USED = "ALREADY_USED"
    WRONG_EVENT = "WRONG_EVENT"


def _sign(ticket_id: str, qr_secret: str) -> str:
    payload = f"{ticket_id}.{qr_secret}"
    return hmac.new(
        settings.QR_SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def render_token(ticket: Ticket) -> str:
    ticket_id = str(ticket.id)
    signature = _sign(ticket_id, ticket.qr_secret)
    return f"{ticket_id}.{ticket.qr_secret}.{signature}"


def issue(ticket: Ticket) -> str:
    ticket.qr_secret = secrets.token_hex(32)
    return render_token(ticket)


def validate(db: Session, raw_token: str, gate_event_id: UUID) -> GateResult:
    parts = raw_token.split(".")
    if len(parts) != 3:
        return GateResult.INVALID

    ticket_id_str, qr_secret, signature = parts
    if not hmac.compare_digest(signature, _sign(ticket_id_str, qr_secret)):
        return GateResult.INVALID

    try:
        ticket_id = UUID(ticket_id_str)
    except ValueError:
        return GateResult.INVALID

    ticket = db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.qr_secret == qr_secret)
    ).scalar_one_or_none()
    if ticket is None:
        return GateResult.INVALID

    if ticket.event_id != gate_event_id:
        return GateResult.WRONG_EVENT

    if ticket.status == TicketStatus.USED:
        return GateResult.ALREADY_USED

    result = db.execute(
        update(Ticket)
        .where(Ticket.id == ticket_id, Ticket.status == TicketStatus.PAID)
        .values(status=TicketStatus.USED, used_at=datetime.now(UTC))
    )
    if result.rowcount == 0:
        db.rollback()
        return GateResult.ALREADY_USED

    db.commit()
    return GateResult.VALID
