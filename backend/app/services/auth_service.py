import jwt
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.models.company import Company
from app.models.user import User
from app.repositories.company import CompanyRepository
from app.repositories.user import UserRepository
from app.schemas.auth import RefreshResponse, TokenResponse


class InvalidCredentialsError(Exception):
    """Raised when login fails, for any reason other than a suspended
    company (see CompanySuspendedError).

    Deliberately does not distinguish "unknown company code" from "unknown
    username" from "wrong password" from "inactive account" - the route
    always turns this into the same 401 response, so a caller can't use the
    error to probe which company codes are valid, which accounts are
    registered, or whether one is disabled.
    """


class CompanyNotFoundError(Exception):
    """Raised by resolve_company when no company matches the given code.

    Unlike login, resolve_company deliberately *does* reveal this
    distinctly (as a 404) - company codes are meant to be shared among a
    company's own employees to type in, not secrets, so confirming a code's
    existence here is standard SaaS UX, not a credential leak. login()
    keeps this folded into the generic InvalidCredentialsError instead;
    see that method's docstring.
    """


class CompanySuspendedError(Exception):
    """Raised when a company exists but has been deactivated
    (is_active=False) - surfaced as a distinct, honest rejection both at
    resolve_company and at login, unlike every other login failure.
    """


class InvalidRefreshTokenError(Exception):
    """Raised when a refresh token is missing, malformed, expired, of the
    wrong type (e.g. an access token was presented), or its user no longer
    exists/is inactive.
    """


class AuthService:
    """Coordinates the login and refresh flows, and issues tokens on behalf
    of company registration (see CompanyService.register_company): locate
    user, verify password, issue tokens.
    """

    def __init__(
        self,
        db: Session,
        user_repository: UserRepository | None = None,
        company_repository: CompanyRepository | None = None,
    ) -> None:
        self._db = db
        self._user_repository = (
            user_repository if user_repository is not None else UserRepository(db)
        )
        self._company_repository = (
            company_repository if company_repository is not None else CompanyRepository(db)
        )

    def resolve_company(self, company_code: str) -> Company:
        """POST /auth/resolve-company: look up a company by its code, for
        the login screen to display before asking for credentials.

        Unlike login(), this deliberately reveals whether a code exists and
        whether it's suspended - see CompanyNotFoundError/
        CompanySuspendedError's docstrings for why that's an acceptable,
        intentional exception to this service's usual non-disclosure.
        """
        company = self._company_repository.get_by_code(company_code)
        if company is None:
            raise CompanyNotFoundError
        if not company.is_active:
            raise CompanySuspendedError
        return company

    def authenticate(self, company_code: str, username: str, password: str) -> User:
        """Return the matching active user in the given company, or raise
        InvalidCredentialsError (or CompanySuspendedError - see class
        docstrings)."""
        company = self._company_repository.get_by_code(company_code)
        if company is None:
            # Folded into the generic credentials error here (unlike
            # resolve_company) so login can't be used to probe which
            # company codes are valid.
            raise InvalidCredentialsError
        if not company.is_active:
            raise CompanySuspendedError
        user = self._user_repository.get_by_username_or_email(username, company.id)
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

    def login(self, company_code: str, username: str, password: str) -> TokenResponse:
        """Authenticate then issue an access + refresh token pair. Read-only."""
        user = self.authenticate(company_code, username, password)
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
