from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.session import get_db
from app.models.ticket import Ticket
from app.models.transfer_invite import TransferInvite
from app.models.user import Role, User
from app.schemas.ticket import TicketRead
from app.schemas.transfer import TransferInviteCreate, TransferInviteRead
from app.services import transfer
from app.services.ticket import TicketNotFoundError, get_owned_ticket

router = APIRouter(tags=["transfers"])


def _invite_or_404(db: Session, token: str) -> TransferInvite:
    try:
        return transfer.get_invite_by_token(db, token)
    except transfer.TransferInviteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transfer invite not found"
        ) from exc


@router.post(
    "/tickets/{ticket_id}/transfers",
    response_model=TransferInviteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_transfer_invite_endpoint(
    ticket_id: UUID,
    payload: TransferInviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> TransferInvite:
    try:
        ticket = get_owned_ticket(db, ticket_id, current_user.id)
    except TicketNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        ) from exc
    try:
        return transfer.create_invite(
            db, ticket.id, current_user.id, payload.to_email
        )
    except transfer.InvalidTicketStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/transfers/incoming", response_model=list[TransferInviteRead])
def list_incoming_transfer_invites_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> list[TransferInvite]:
    return transfer.list_incoming(db, current_user.email)


@router.get("/transfers/outgoing", response_model=list[TransferInviteRead])
def list_outgoing_transfer_invites_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> list[TransferInvite]:
    return transfer.list_outgoing(db, current_user.id)


@router.get("/transfers/{token}", response_model=TransferInviteRead)
def view_transfer_invite_endpoint(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> TransferInvite:
    return _invite_or_404(db, token)


@router.post("/transfers/{token}/accept", response_model=TicketRead)
def accept_transfer_invite_endpoint(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> Ticket:
    try:
        return transfer.accept(db, token, current_user.id)
    except transfer.TransferInviteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (
        transfer.TransferInviteNotPendingError,
        transfer.TransferInviteExpiredError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail=str(exc)
        ) from exc
    except transfer.InvalidTicketStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/transfers/{token}/decline", response_model=TransferInviteRead)
def decline_transfer_invite_endpoint(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> TransferInvite:
    try:
        return transfer.decline(db, token)
    except transfer.TransferInviteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except transfer.TransferInviteNotPendingError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail=str(exc)
        ) from exc


@router.post("/transfers/{token}/cancel", response_model=TransferInviteRead)
def cancel_transfer_invite_endpoint(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.CUSTOMER)),
) -> TransferInvite:
    try:
        return transfer.cancel_invite(db, token, current_user.id)
    except transfer.TransferInviteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except transfer.TransferInviteForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except transfer.TransferInviteNotPendingError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail=str(exc)
        ) from exc
