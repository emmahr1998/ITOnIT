from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse


class InvalidCredentialsError(Exception):
    """Raised when login fails, for any reason.

    Deliberately does not distinguish "unknown email" from "wrong password"
    from "inactive account" - the route always turns this into the same
    401 response, so a caller can't use the error to probe which emails
    are registered or whether an account is disabled.
    """


class AuthService:
    """Coordinates the login flow: locate user, verify password, issue token."""

    def __init__(self, db: Session, user_repository: UserRepository | None = None) -> None:
        self._user_repository = (
            user_repository if user_repository is not None else UserRepository(db)
        )

    def authenticate(self, email: str, password: str) -> User:
        """Return the matching active user, or raise InvalidCredentialsError."""
        user = self._user_repository.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InvalidCredentialsError
        return user

    def issue_token(self, user: User) -> TokenResponse:
        access_token = create_access_token(subject=user.id)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate then issue a token. Read-only: never commits."""
        user = self.authenticate(email, password)
        return self.issue_token(user)
