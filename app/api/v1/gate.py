from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.seat import Seat
from app.models.ticket import Ticket
from app.models.user import Role, User
from app.schemas.event import SeatRead
from app.schemas.gate import GateValidateRequest, GateValidateResponse
from app.services.ticketing import GateResult, validate

router = APIRouter(prefix="/gate", tags=["gate"])


def _parse_ticket_id(raw_token: str) -> UUID | None:
    parts = raw_token.split(".")
    if len(parts) != 3:
        return None
    try:
        return UUID(parts[0])
    except ValueError:
        return None


@router.post("/validate", response_model=GateValidateResponse)
def validate_ticket_endpoint(
    payload: GateValidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.GATE_STAFF)),
) -> GateValidateResponse:
    result = validate(db, payload.raw_code, payload.event_id)

    if result != GateResult.VALID:
        return GateValidateResponse(result=result)

    ticket_id = _parse_ticket_id(payload.raw_code)
    ticket = db.get(Ticket, ticket_id) if ticket_id is not None else None
    seat = db.get(Seat, ticket.seat_id) if ticket is not None else None
    customer = db.get(User, ticket.owner_id) if ticket is not None else None

    return GateValidateResponse(
        result=result,
        ticket_id=ticket.id if ticket is not None else None,
        seat=SeatRead.model_validate(seat) if seat is not None else None,
        customer_name=customer.name if customer is not None else None,
        customer_email=customer.email if customer is not None else None,
    )
