import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Role(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    ORGANIZER = "ORGANIZER"
    GATE_STAFF = "GATE_STAFF"


class User(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
