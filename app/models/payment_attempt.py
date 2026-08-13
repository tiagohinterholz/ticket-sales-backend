import enum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class PaymentResult(str, enum.Enum):
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"


class PaymentAttempt(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "payment_attempts"

    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    card_last4: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[PaymentResult] = mapped_column(
        Enum(PaymentResult, name="payment_result"), nullable=False
    )
