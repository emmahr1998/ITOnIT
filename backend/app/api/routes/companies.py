import mimetypes

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from starlette.responses import Response

from app.dependencies import get_auth_service, get_company_service, get_current_company_id, require_roles
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.company import (
    CompanyRegisterRequest,
    CompanySettingsResponse,
    CompanyUpdateRequest,
    company_logo_url,
)
from app.services.auth_service import AuthService
from app.services.company_service import (
    CompanyCodeConflictError,
    CompanyNotFoundError,
    CompanyService,
    InvalidLogoError,
    LogoNotFoundError,
)

router = APIRouter(prefix="/companies", tags=["Companies"])

_MANAGE_ROLES = ("Company Administrator",)


def _to_settings_response(company: Company) -> CompanySettingsResponse:
    return CompanySettingsResponse(
        id=company.id,
        name=company.name,
        company_code=company.company_code,
        contact_email=company.contact_email,
        logo_url=company_logo_url(company.id, company.logo_path),
        theme=company.theme,
        timezone=company.timezone,
        language=company.language,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_company(
    payload: CompanyRegisterRequest,
    company_service: CompanyService = Depends(get_company_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Public. Register a new company: creates the company, its first
    Company Administrator, and starter company data in one transaction,
    then signs the new Company Administrator in immediately - see
    CompanyService.register_company.

    Replaces the old POST /auth/register self-registration flow, which
    always created a bare, company-less Employee account.
    """
    try:
        admin = company_service.register_company(payload)
    except CompanyCodeConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A company with this company code already exists"
        ) from exc
    return auth_service.issue_tokens(admin)


@router.get("/me", response_model=CompanySettingsResponse)
def get_company_settings(
    company_id: int = Depends(get_current_company_id),
    company_service: CompanyService = Depends(get_company_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> CompanySettingsResponse:
    """Company-Administrator-only. company_id always comes from the
    authenticated caller's own row (get_current_company_id), never from
    client input - there is no System Administrator handling here, since a
    System Administrator has no company_id at all and is rejected by
    get_current_company_id before this route body ever runs.
    """
    return _to_settings_response(company_service.get_company(company_id))


@router.patch("/me", response_model=CompanySettingsResponse)
def update_company_settings(
    payload: CompanyUpdateRequest,
    company_id: int = Depends(get_current_company_id),
    company_service: CompanyService = Depends(get_company_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> CompanySettingsResponse:
    try:
        company = company_service.update_company(company_id, payload)
    except CompanyCodeConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A company with this company code already exists"
        ) from exc
    return _to_settings_response(company)


@router.post("/me/logo", response_model=CompanySettingsResponse)
async def upload_company_logo(
    file: UploadFile = File(...),
    company_id: int = Depends(get_current_company_id),
    company_service: CompanyService = Depends(get_company_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> CompanySettingsResponse:
    content = await file.read()
    try:
        company = company_service.upload_logo(company_id, file.filename or "logo", content)
    except InvalidLogoError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _to_settings_response(company)


@router.get("/{company_id}/logo")
def get_company_logo(
    company_id: int,
    company_service: CompanyService = Depends(get_company_service),
) -> Response:
    """Public, unauthenticated - a company's own logo isn't sensitive, and
    the pre-login screen needs to display it before any credentials are
    entered (same non-disclosure exception as POST /auth/resolve-company).
    """
    try:
        stored_filename, content = company_service.get_logo(company_id)
    except (CompanyNotFoundError, LogoNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Logo not found") from exc
    content_type = mimetypes.guess_type(stored_filename)[0] or "application/octet-stream"
    return Response(content=content, media_type=content_type)
