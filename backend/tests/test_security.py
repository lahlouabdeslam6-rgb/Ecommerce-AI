from jwt import InvalidTokenError
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing() -> None:
    hashed = hash_password("StrongPassword!2026")
    assert hashed != "StrongPassword!2026"
    assert verify_password("StrongPassword!2026", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_and_refresh_tokens_have_separate_types() -> None:
    access = create_access_token(user_id=12, role="admin", token_version=3)
    refresh = create_refresh_token(user_id=12, role="admin", token_version=3)
    access_payload = decode_token(access, "access")
    refresh_payload = decode_token(refresh, "refresh")
    assert access_payload["sub"] == "12"
    assert access_payload["ver"] == 3
    assert refresh_payload["type"] == "refresh"
    with pytest.raises(InvalidTokenError):
        decode_token(refresh, "access")
