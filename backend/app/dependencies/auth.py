from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.roles import SYSTEM_ADMINISTRATOR_ROLE
from app.core.security import decode_access_token
from app.dependencies.database import get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService

# auto_error=False so a missing token reaches our own 401 handling below,
# instead of FastAPI's default (403) for a missing Authorization header.
bearer_scheme = HTTPBearer(auto_error=False)


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    """Resolve the authenticated user from a Bearer token, or fail with 401."""
    if credentials is None:
        raise _credentials_error()

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.sub)
    except (jwt.PyJWTError, ValueError) as exc:
        raise _credentials_error() from exc

    user = user_repository.get_by_id(user_id)
    if user is None:
        raise _credentials_error()

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Same as get_current_user, but also rejects deactivated accounts and
    accounts whose company has been suspended.

    The company check runs fresh on every request (current_user.company is
    eager-loaded by UserRepository.get_by_id, not lazy-loaded), not just at
    login - suspending a company immediately revokes access for all of its
    users, even ones holding a still-valid, unexpired access token. The
    System Administrator's own company is the platform company, which
    PlatformService never lets anyone deactivate, so this check can't lock
    the platform account out. A legacy company-less row (company_id is
    None) has no company to check here.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user.company_id is not None and not current_user.company.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This company's account has been suspended",
        )
    return current_user


def get_current_company_id(current_user: User = Depends(get_current_active_user)) -> int:
    """The one place every tenant-scoped repository/service gets its
    company_id from - always derived from the authenticated user's own row,
    never from a client-supplied header/param/body field, anywhere.

    Every tenant user has a company. The System Administrator belongs to
    the platform company (Company.is_platform), which is not a tenant: it is
    served exclusively by the /platform routes and is refused here, so the
    platform account can never read or write tenant-scoped data through an
    ordinary tenant route - its cross-company access exists only where
    require_system_administrator explicitly grants it. A company-less
    account is refused the same way rather than silently returning None: a
    `WHERE company_id = NULL` query would just as safely return nothing,
    but failing loudly makes it obvious the route is tenant-only, not that
    data quietly vanished.
    """
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has no associated company",
        )
    if current_user.company is not None and current_user.company.is_platform:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform accounts cannot access company workspaces",
        )
    return current_user.company_id


def require_system_administrator(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """The only gate on every protected /platform route - the one place
    platform-wide (cross-company) access is granted.

    Deliberately stricter than require_roles("System Administrator"): a role
    name alone is not enough, since role_id is just a column a tenant user
    can end up pointing at by mistake. Access requires all three of the
    System Administrator role, the is_system_administrator flag (unique
    across the whole users table), and membership of the platform company.
    Any mismatch between them fails closed with the same 403.
    """
    is_platform_member = current_user.company is not None and bool(
        current_user.company.is_platform
    )
    if not (
        current_user.role.name == SYSTEM_ADMINISTRATOR_ROLE
        and current_user.is_system_administrator
        and is_platform_member
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    return current_user


def require_roles(*allowed_role_names: str) -> Callable[..., User]:
    """Build a dependency that only allows users whose role is in allowed_role_names.

    Usage: Depends(require_roles("Company Administrator"))
    Role names must match app.models.role.Role.name exactly - one of
    app.core.roles.COMPANY_ROLE_NAMES. Never use this for System
    Administrator access; that is require_system_administrator's job.
    """

    def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role.name not in allowed_role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return dependency
