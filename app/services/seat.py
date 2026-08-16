from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.seat import Seat


def list_for_event(db: Session, event_id: UUID) -> list[Seat]:
    return list(
        db.execute(
            select(Seat)
            .where(Seat.event_id == event_id)
            .order_by(Seat.row_label, Seat.seat_number)
        ).scalars()
    )
