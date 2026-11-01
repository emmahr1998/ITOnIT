from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import (
    get_auth_service,
    get_platform_service,
    require_system_administrator,
)
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.company import PlatformCompanyRegisterRequest
from app.schemas.platform import (
    CompanyDetailResponse,
    CompanyListResponse,
    CompanySummaryResponse,
    PlatformLoginRequest,
    PlatformOverviewResponse,
)
from app.schemas.response import DataResponse
from app.services.auth_service import AuthService, InvalidCredentialsError
from app.services.company_service import CompanyCodeConflictError
from app.services.platform_service import CompanyNotFoundError, PlatformService

router = APIRouter(prefix="/platform", tags=["Platform"])

# Every route below except /login depends on require_system_administrator -
# never require_roles("System Administrator"), which checks the role name
# only. That guard also requires the is_system_administrator flag and
# platform-company membership, so a tenant user whose role_id was changed
# to System Administrator gets no platform access at all. No route depends
# on get_current_company_id: a company_id in a URL below identifies the
# customer company being inspected, never authorization.


@router.post("/login", response_model=TokenResponse)
def platform_login(
    payload: PlatformLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Public - the one route in this router with no
    require_roles(...) dependency, since there is no authenticated caller
    yet (Milestone 8, Phase 8.3). Resolves ONLY the flagged System
    Administrator account in the platform company - see
    AuthService.authenticate_platform_administrator and
    UserRepository.get_platform_administrator. Never accepts a
    company_code; this is not a tenant login and never falls back to one.
    """
    try:
        return auth_service.login_platform_administrator(payload.username, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/companies",
    response_model=DataResponse[CompanyDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_platform_company(
    payload: PlatformCompanyRegisterRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    _current_user: User = Depends(require_system_administrator),
) -> DataResponse[CompanyDetailResponse]:
    """System-Administrator-only (Milestone 8, Phase 8.4). Uses its own
    request schema (PlatformCompanyRegisterRequest) that, unlike public
    self-registration's CompanyRegisterRequest, requires an explicit
    company_code - and the exact same CompanyService.register_company call
    self-service POST /companies/register uses, just passing that code
    through - no parallel creation logic exists here, see
    PlatformService.create_company's own docstring. Unlike
    self-registration, no tokens are returned: a System Administrator
    provisioning a company on a customer's behalf is never signed in as
    that company's new admin."""
    try:
        detail = platform_service.create_company(payload)
    except CompanyCodeConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A company with this company code already exists"
        ) from exc
    return DataResponse(
        data=CompanyDetailResponse.from_domain(detail),
        msg="Company created successfully",
    )


@router.get("/overview", response_model=DataResponse[PlatformOverviewResponse])
def get_platform_overview(
    platform_service: PlatformService = Depends(get_platform_service),
    _current_user: User = Depends(require_system_administrator),
) -> DataResponse[PlatformOverviewResponse]:
    overview = platform_service.get_overview()
    return DataResponse(
        data=PlatformOverviewResponse.from_domain(overview),
        msg="Platform overview fetched successfully",
    )


@router.get("/companies", response_model=CompanyListResponse)
def list_platform_companies(
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    platform_service: PlatformService = Depends(get_platform_service),
    _current_user: User = Depends(require_system_administrator),
) -> CompanyListResponse:
    companies, total = platform_service.list_companies(
        search=search,
        is_active=is_active,
        sort_by=sort_by,
        sort_dir=sort_dir,
        skip=skip,
        limit=limit,
    )
    return CompanyListResponse(
        data=[CompanySummaryResponse.model_validate(c) for c in companies],
        total=total,
        msg=f"Fetched {len(companies)} of {total} companies",
    )


@router.get("/companies/{company_id}", response_model=DataResponse[CompanyDetailResponse])
def get_platform_company_detail(
    company_id: int,
    platform_service: PlatformService = Depends(get_platform_service),
    _current_user: User = Depends(require_system_administrator),
) -> DataResponse[CompanyDetailResponse]:
    try:
        detail = platform_service.get_company_detail(company_id)
    except CompanyNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found") from exc
    return DataResponse(
        data=CompanyDetailResponse.from_domain(detail),
        msg="Company detail fetched successfully",
    )


@router.patch(
    "/companies/{company_id}/activate", response_model=DataResponse[CompanyDetailResponse]
)
def activate_platform_company(
    company_id: int,
    platform_service: PlatformService = Depends(get_platform_service),
    _current_user: User = Depends(require_system_administrator),
) -> DataResponse[CompanyDetailResponse]:
    """Idempotent - activating an already-active company still succeeds.
    Only flips Company.is_active; see PlatformService.set_company_active's
    docstring for why every access-control consequence of that flip is
    enforced by existing auth code, not by anything this route or service
    does directly."""
    try:
        detail = platform_service.set_company_active(company_id, True)
    except CompanyNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found") from exc
    return DataResponse(
        data=CompanyDetailResponse.from_domain(detail),
        msg="Company activated successfully",
    )


@router.patch(
    "/companies/{company_id}/deactivate", response_model=DataResponse[CompanyDetailResponse]
)
def deactivate_platform_company(
    company_id: int,
    platform_service: PlatformService = Depends(get_platform_service),
    _current_user: User = Depends(require_system_administrator),
) -> DataResponse[CompanyDetailResponse]:
    """Idempotent - deactivating an already-inactive company still
    succeeds. Never deletes or mutates any tenant data (users, tickets,
    inventory, settings) - only Company.is_active changes. Suspends the
    tenant's access via the existing, unmodified checks in
    AuthService.resolve_company/authenticate (blocks new logins) and
    get_current_active_user (blocks every already-authenticated request,
    including ones holding a still-valid, unexpired access token)."""
    try:
        detail = platform_service.set_company_active(company_id, False)
    except CompanyNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found") from exc
    return DataResponse(
        data=CompanyDetailResponse.from_domain(detail),
        msg="Company deactivated successfully",
    )
