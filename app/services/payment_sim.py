from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.timeutils import as_utc
from app.models.payment_attempt import PaymentAttempt, PaymentResult
from app.models.ticket import Ticket, TicketStatus
from app.services import ticketing


class HoldExpiredError(Exception):
    pass


@dataclass
class PaymentOutcome:
    ticket: Ticket
    payment_attempt: PaymentAttempt


def attempt_payment(db: Session, ticket_id: UUID, card_number: str) -> PaymentOutcome:
    ticket = db.get(Ticket, ticket_id)
    now = datetime.now(UTC)
    hold_still_open = (
        ticket is not None
        and ticket.status == TicketStatus.HELD
        and ticket.expires_at is not None
        and as_utc(ticket.expires_at) >= now
    )
    if not hold_still_open:
        raise HoldExpiredError("Hold has expired")

    declined = card_number.endswith("0000")
    result = PaymentResult.DECLINED if declined else PaymentResult.APPROVED

    payment_attempt = PaymentAttempt(
        ticket_id=ticket.id,
        card_last4=card_number[-4:],
        result=result,
    )
    db.add(payment_attempt)

    if not declined:
        ticket.status = TicketStatus.PAID
        ticket.paid_at = now
        ticketing.issue(ticket)

    db.commit()
    db.refresh(ticket)
    db.refresh(payment_attempt)
    return PaymentOutcome(ticket=ticket, payment_attempt=payment_attempt)
