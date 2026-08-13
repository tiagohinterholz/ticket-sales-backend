from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    require_role,
    verify_password,
)
from app.models.user import Role, User


def make_user(role: Role = Role.CUSTOMER) -> User:
    return User(
        id=uuid4(),
        email="user@example.com",
        password_hash="irrelevant",
        role=role,
        name="Test User",
    )


class TestPasswordHashing:
    def test_verify_password_roundtrip_returns_true_for_correct_password(self):
        plain = "correct-horse-battery-staple"
        assert verify_password(plain, hash_password(plain)) is True

    def test_verify_password_returns_false_for_wrong_password(self):
        password_hash = hash_password("correct-horse-battery-staple")
        assert verify_password("wrong-password", password_hash) is False


class TestJWTRoundtrip:
    def test_decode_of_created_token_returns_matching_sub_and_role_claims(self):
        user = make_user(role=Role.ORGANIZER)
        token = create_access_token(user)

        claims = decode_access_token(token)

        assert claims["sub"] == str(user.id)
        assert claims["role"] == Role.ORGANIZER.value

    def test_expired_token_is_rejected(self):
        now = datetime.now(UTC)
        expired_payload = {
            "sub": str(uuid4()),
            "role": Role.CUSTOMER.value,
            "iat": now - timedelta(minutes=120),
            "exp": now - timedelta(minutes=60),
        }
        expired_token = jwt.encode(
            expired_payload, settings.JWT_SECRET, algorithm=ALGORITHM
        )

        with pytest.raises(jwt.PyJWTError):
            decode_access_token(expired_token)

    def test_tampered_token_signature_is_rejected(self):
        user = make_user()
        token = create_access_token(user)
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

        with pytest.raises(jwt.PyJWTError):
            decode_access_token(tampered)


class TestRequireRoleGuard:
    def test_require_role_allows_matching_role(self):
        user = make_user(role=Role.GATE_STAFF)
        guard = require_role(Role.GATE_STAFF)

        result = guard(user)

        assert result is user

    def test_require_role_blocks_non_matching_role_with_403(self):
        user = make_user(role=Role.CUSTOMER)
        guard = require_role(Role.ORGANIZER)

        with pytest.raises(HTTPException) as exc_info:
            guard(user)

        assert exc_info.value.status_code == 403

    def test_require_role_allows_any_of_multiple_permitted_roles(self):
        user = make_user(role=Role.ORGANIZER)
        guard = require_role(Role.ORGANIZER, Role.GATE_STAFF)

        result = guard(user)

        assert result is user
