from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.payment import PaymentPayRead, PaymentRequest
from app.services.payment_sim import HoldExpiredError, attempt_payment
from app.services.ticket import TicketNotFoundError, get_owned_ticket

router = APIRouter(prefix="/tickets", tags=["payments"])


@router.post("/{ticket_id}/pay", response_model=PaymentPayRead)
def pay_ticket_endpoint(
    ticket_id: UUID,
    payload: PaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> PaymentPayRead:
    try:
        get_owned_ticket(db, ticket_id, current_user.id)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        ) from exc

    try:
        outcome = attempt_payment(db, ticket_id, payload.card_number)
    except HoldExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="Hold has expired"
        ) from exc

    return PaymentPayRead(status=outcome.payment_attempt.result, ticket=outcome.ticket)
