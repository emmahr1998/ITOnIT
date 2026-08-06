import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.schemas.auth import RefreshResponse, RegisterRequest, TokenResponse

# Every self-registered account is created with this role, never one chosen
# by the client - see RegisterRequest's own docstring for why.
_SELF_REGISTER_ROLE_NAME = "Employee"


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


class UsernameConflictError(Exception):
    """Raised when a registration's username is already taken."""


class EmailConflictError(Exception):
    """Raised when a registration's email is already taken."""


class AuthService:
    """Coordinates the login, refresh, and self-registration flows: locate
    user, verify password, issue tokens.
    """

    def __init__(
        self,
        db: Session,
        user_repository: UserRepository | None = None,
        role_repository: RoleRepository | None = None,
    ) -> None:
        self._db = db
        self._user_repository = (
            user_repository if user_repository is not None else UserRepository(db)
        )
        self._role_repository = (
            role_repository if role_repository is not None else RoleRepository(db)
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

    def register(self, payload: RegisterRequest) -> TokenResponse:
        """Create a new Employee-role account and sign them in immediately.

        Public, unauthenticated endpoint - no admin approval or email
        verification step exists in this project. Role is always Employee
        (see _SELF_REGISTER_ROLE_NAME); a client can never self-assign
        Technician/Manager/Administrator through this path.
        """
        if self._user_repository.get_by_username(payload.username) is not None:
            raise UsernameConflictError
        if self._user_repository.get_by_email(payload.email) is not None:
            raise EmailConflictError

        role = self._role_repository.get_by_name(_SELF_REGISTER_ROLE_NAME)
        if role is None:
            # Seeded roles are a deployment invariant, not user input - a
            # missing Employee role means the database was never seeded.
            raise RuntimeError(f"Role '{_SELF_REGISTER_ROLE_NAME}' is not seeded")

        user = User(
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            role_id=role.id,
            password_hash=hash_password(payload.password),
            is_active=True,
        )
        user.role = role
        try:
            self._user_repository.create(user)
            self._db.commit()
        except IntegrityError as exc:
            # Defense in depth: a concurrent request could pass the checks
            # above and lose the race to the database's unique constraints.
            self._db.rollback()
            raise UsernameConflictError from exc

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
