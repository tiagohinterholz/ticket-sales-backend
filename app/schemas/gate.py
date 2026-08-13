from uuid import UUID

from pydantic import BaseModel, model_validator

from app.schemas.event import SeatRead
from app.services.ticketing import GateResult


class GateValidateRequest(BaseModel):
    event_id: UUID
    token: str | None = None
    manual_code: str | None = None

    @model_validator(mode="after")
    def check_token_or_manual_code(self) -> "GateValidateRequest":
        if not self.token and not self.manual_code:
            raise ValueError("token or manual_code is required")
        return self

    @property
    def raw_code(self) -> str:
        return self.token or self.manual_code


class GateValidateResponse(BaseModel):
    result: GateResult
    ticket_id: UUID | None = None
    seat: SeatRead | None = None
    customer_name: str | None = None
    customer_email: str | None = None
