import jwt
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import RefreshResponse, TokenResponse


class InvalidCredentialsError(Exception):
    """Raised when login fails, for any reason.

    Deliberately does not distinguish "unknown username" from "wrong
    password" from "inactive account" - the route always turns this into
    the same 401 response, so a caller can't use the error to probe which
    accounts are registered or whether one is disabled.
    """


class InvalidRefreshTokenError(Exception):
    """Raised when a refresh token is missing, malformed, expired, of the
    wrong type (e.g. an access token was presented), or its user no longer
    exists/is inactive.
    """


class AuthService:
    """Coordinates the login and refresh flows: locate user, verify
    password, issue tokens.
    """

    def __init__(self, db: Session, user_repository: UserRepository | None = None) -> None:
        self._user_repository = (
            user_repository if user_repository is not None else UserRepository(db)
        )

    def authenticate(self, username: str, password: str) -> User:
        """Return the matching active user, or raise InvalidCredentialsError."""
        user = self._user_repository.get_by_username_or_email(username)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InvalidCredentialsError
        return user

    def issue_tokens(self, user: User) -> TokenResponse:
        return TokenResponse(
            access=create_access_token(subject=user.id),
            refresh=create_refresh_token(subject=user.id),
            token_type="bearer",
        )

    def login(self, username: str, password: str) -> TokenResponse:
        """Authenticate then issue an access + refresh token pair. Read-only."""
        user = self.authenticate(username, password)
        return self.issue_tokens(user)

    def refresh_access_token(self, refresh_token: str) -> RefreshResponse:
        """Validate a refresh token and issue a new access token.

        Rejects anything that isn't a valid, unexpired, "type": "refresh"
        token (an access token presented here fails its type check), and
        rejects tokens belonging to a user that no longer exists or has
        been deactivated since the token was issued.
        """
        try:
            payload = decode_refresh_token(refresh_token)
            user_id = int(payload.sub)
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidRefreshTokenError from exc

        user = self._user_repository.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError

        return RefreshResponse(access=create_access_token(subject=user.id), token_type="bearer")
