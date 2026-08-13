from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.transfer_invite import TransferInviteStatus
from app.schemas.base import BaseReadSchema


class TransferInviteCreate(BaseModel):
    to_email: str = Field(min_length=1)


class TransferInviteRead(BaseReadSchema):
    ticket_id: UUID
    from_user_id: UUID
    to_email: str
    to_user_id: UUID | None
    token: str
    status: TransferInviteStatus
    expires_at: datetime
