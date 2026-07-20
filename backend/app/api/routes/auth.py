from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_auth_service, get_current_active_user
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse
from app.services.auth_service import AuthService, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """Authenticate with email + password and receive a JWT access token."""
    try:
        return auth_service.login(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: User = Depends(get_current_active_user),
) -> CurrentUserResponse:
    """Return the authenticated user's own profile."""
    return CurrentUserResponse.model_validate(current_user)
