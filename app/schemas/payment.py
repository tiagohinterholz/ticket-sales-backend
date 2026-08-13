from pydantic import BaseModel

from app.models.payment_attempt import PaymentResult
from app.schemas.ticket import TicketRead


class PaymentRequest(BaseModel):
    card_number: str


class PaymentPayRead(BaseModel):
    status: PaymentResult
    ticket: TicketRead
