from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.schemas.auth import TokenPayload

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plaintext password using the recommended Argon2 scheme."""
    return _password_hash.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored hash."""
    return _password_hash.verify(plain_password, password_hash)


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token for the given subject (typically a user id).

    No sensitive user data goes into the payload - only the subject and timing claims.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": str(subject), "iat": now, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token, returning its payload.

    Raises jwt.PyJWTError (or a subclass, e.g. ExpiredSignatureError,
    DecodeError) for expired, malformed, or otherwise invalid tokens,
    including a token whose 'sub' claim is missing or empty.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    subject = payload.get("sub")
    if not subject:
        raise jwt.InvalidTokenError("Token is missing a subject")
    return TokenPayload(sub=subject, exp=payload["exp"], iat=payload.get("iat"))
