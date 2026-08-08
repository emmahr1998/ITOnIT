from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

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
    users, even ones holding a still-valid, unexpired access token. A user
    with no company (company_id is None - reserved for the future System
    Administrator, who logs in through a separate /platform/login rather
    than this dependency chain at all) has nothing to check here.
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

    Every user reachable through this dependency has a company today
    (company_id is nullable on User only to make room for a future,
    platform-level System Administrator account, which does not exist yet
    and has no route that could reach this dependency). Raising here rather
    than silently returning None if that ever changed without a
    corresponding route change is deliberate: a `WHERE company_id = NULL`
    query would just as safely return nothing, but failing loudly is a
    clearer signal that a route needs the not-yet-built System
    Administrator exception, not that data quietly vanished.
    """
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has no associated company",
        )
    return current_user.company_id


def require_roles(*allowed_role_names: str) -> Callable[..., User]:
    """Build a dependency that only allows users whose role is in allowed_role_names.

    Usage: Depends(require_roles("Company Administrator"))
    Role names must match app.models.role.Role.name exactly, e.g. one of the
    roles seeded by app.scripts.seed_initial_data: Employee, Technician,
    Company Administrator, System Administrator.
    """

    def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role.name not in allowed_role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return dependency
