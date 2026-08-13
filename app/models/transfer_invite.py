import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class TransferInviteStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class TransferInvite(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "transfer_invites"

    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    from_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    to_email: Mapped[str] = mapped_column(String, nullable=False)
    to_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    status: Mapped[TransferInviteStatus] = mapped_column(
        Enum(TransferInviteStatus, name="transfer_invite_status"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
