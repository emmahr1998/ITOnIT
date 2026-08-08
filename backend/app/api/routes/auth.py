from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_auth_service, get_current_active_user
from app.models.user import User
from app.schemas.auth import (
    CompanyCodeRequest,
    CompanyResolveResponse,
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_service import (
    AuthService,
    CompanyNotFoundError,
    CompanySuspendedError,
    EmailConflictError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UsernameConflictError,
)

_COMPANY_SUSPENDED_DETAIL = "This company's account has been suspended"

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


@router.post("/resolve-company", response_model=CompanyResolveResponse)
def resolve_company(
    payload: CompanyCodeRequest, auth_service: AuthService = Depends(get_auth_service)
) -> CompanyResolveResponse:
    """Public. Look up a company by its code so a login screen can show
    which company a caller is signing into before asking for credentials.

    Unlike /auth/login, this deliberately reveals whether the code exists
    and whether the company is suspended - see AuthService.resolve_company.
    """
    try:
        company = auth_service.resolve_company(payload.company_code)
    except CompanyNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found") from exc
    except CompanySuspendedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _COMPANY_SUSPENDED_DETAIL) from exc
    return CompanyResolveResponse(company_name=company.name, company_logo=company.logo_path)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """Authenticate with a company code + username (or email) + password
    and receive a JWT access + refresh token pair.
    """
    try:
        return auth_service.login(payload.company_code, payload.username, payload.password)
    except CompanySuspendedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _COMPANY_SUSPENDED_DETAIL) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid company code, username, or password",
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
