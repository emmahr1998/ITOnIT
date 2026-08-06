from datetime import timedelta

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

PASSWORD = "CorrectHorseBattery1!"


def test_hash_password_differs_from_plaintext() -> None:
    assert hash_password(PASSWORD) != PASSWORD


def test_verify_password_accepts_correct_password() -> None:
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


def test_verify_password_rejects_incorrect_password() -> None:
    assert verify_password("wrong-password", hash_password(PASSWORD)) is False


def test_access_token_round_trips_subject() -> None:
    token = create_access_token(subject=42)
    payload = decode_access_token(token)
    assert payload.sub == "42"


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token(subject=1, expires_delta=timedelta(seconds=-1))
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_malformed_token_is_rejected() -> None:
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("not-a-real-token")
