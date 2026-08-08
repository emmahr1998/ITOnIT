from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_auth_service, get_company_service
from app.schemas.auth import TokenResponse
from app.schemas.company import CompanyRegisterRequest
from app.services.auth_service import AuthService
from app.services.company_service import CompanyCodeConflictError, CompanyService

router = APIRouter(prefix="/companies", tags=["Companies"])


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
