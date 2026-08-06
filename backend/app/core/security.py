from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.schemas.auth import TokenPayload

_password_hash = PasswordHash.recommended()

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    """Hash a plaintext password using the recommended Argon2 scheme."""
    return _password_hash.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored hash."""
    return _password_hash.verify(plain_password, password_hash)


def _create_token(subject: str | int, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    payload = {"sub": str(subject), "type": token_type, "iat": now, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    """Create a signed, short-lived JWT access token for the given subject.

    No sensitive user data goes into the payload - only the subject, a
    "type": "access" claim (so a refresh token can never be used here),
    and timing claims.
    """
    return _create_token(
        subject,
        ACCESS_TOKEN_TYPE,
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    """Create a signed, longer-lived JWT refresh token for the given subject.

    Carries a "type": "refresh" claim so it can never be accepted where an
    access token is required, and vice versa.
    """
    return _create_token(
        subject,
        REFRESH_TOKEN_TYPE,
        expires_delta or timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )


def _decode_token(token: str, expected_type: str) -> TokenPayload:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    subject = payload.get("sub")
    if not subject:
        raise jwt.InvalidTokenError("Token is missing a subject")
    token_type = payload.get("type")
    if token_type != expected_type:
        raise jwt.InvalidTokenError(f"Expected a {expected_type} token")
    return TokenPayload(
        sub=subject, exp=payload["exp"], iat=payload.get("iat"), type=token_type
    )


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token, returning its payload.

    Raises jwt.PyJWTError (or a subclass, e.g. ExpiredSignatureError,
    DecodeError, InvalidTokenError) for expired, malformed, or otherwise
    invalid tokens - including a refresh token presented here, since its
    "type" claim won't match.
    """
    return _decode_token(token, ACCESS_TOKEN_TYPE)


def decode_refresh_token(token: str) -> TokenPayload:
    """Decode and validate a JWT refresh token, returning its payload.

    Raises jwt.PyJWTError (or a subclass) for expired, malformed, or
    otherwise invalid tokens - including an access token presented here.
    """
    return _decode_token(token, REFRESH_TOKEN_TYPE)
