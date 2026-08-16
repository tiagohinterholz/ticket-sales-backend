from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.event import SeatRead
from app.schemas.gate import GateValidateRequest, GateValidateResponse
from app.services.ticketing import (
    GateResult,
    get_gate_details,
    parse_ticket_id,
    validate,
)

router = APIRouter(prefix="/gate", tags=["gate"])


@router.post("/validate", response_model=GateValidateResponse)
def validate_ticket_endpoint(
    payload: GateValidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.GATE_STAFF)),
) -> GateValidateResponse:
    result = validate(db, payload.raw_code, payload.event_id)

    if result == GateResult.ALREADY_USED:
        ticket_id = parse_ticket_id(payload.raw_code)
        details = get_gate_details(db, ticket_id) if ticket_id is not None else None
        return GateValidateResponse(
            result=result,
            used_at=details.ticket.used_at if details is not None else None,
        )

    if result != GateResult.VALID:
        return GateValidateResponse(result=result)

    ticket_id = parse_ticket_id(payload.raw_code)
    details = get_gate_details(db, ticket_id) if ticket_id is not None else None

    return GateValidateResponse(
        result=result,
        ticket_id=details.ticket.id if details is not None else None,
        seat=(
            SeatRead.model_validate(details.seat)
            if details is not None and details.seat is not None
            else None
        ),
        customer_name=(
            details.customer.name
            if details is not None and details.customer is not None
            else None
        ),
        customer_email=(
            details.customer.email
            if details is not None and details.customer is not None
            else None
        ),
        used_at=details.ticket.used_at if details is not None else None,
    )
