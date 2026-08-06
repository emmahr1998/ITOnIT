from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_auth_service, get_current_active_user
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_service import (
    AuthService,
    EmailConflictError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UsernameConflictError,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest, auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """Public self-registration. Always creates an Employee-role account and
    signs the new user in immediately - see AuthService.register.
    """
    try:
        return auth_service.register(payload)
    except UsernameConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A user with this username already exists"
        ) from exc
    except EmailConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A user with this email already exists"
        ) from exc


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """Authenticate with username (or email) + password and receive a JWT
    access + refresh token pair.
    """
    try:
        return auth_service.login(payload.username, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    payload: RefreshRequest, auth_service: AuthService = Depends(get_auth_service)
) -> RefreshResponse:
    """Exchange a valid refresh token for a new access token."""
    try:
        return auth_service.refresh_access_token(payload.refresh)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: User = Depends(get_current_active_user),
) -> CurrentUserResponse:
    """Return the authenticated user's own profile."""
    return CurrentUserResponse.model_validate(current_user)
