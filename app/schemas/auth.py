from pydantic import BaseModel

from app.models.user import Role
from app.schemas.base import BaseReadSchema


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseReadSchema):
    email: str
    name: str
    role: Role
