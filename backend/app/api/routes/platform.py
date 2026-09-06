from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_platform_service, require_roles
from app.models.user import User
from app.schemas.platform import (
    CompanyDetailResponse,
    CompanySummaryResponse,
    PlatformOverviewResponse,
)
from app.schemas.response import DataResponse
from app.services.platform_service import CompanyNotFoundError, PlatformService

router = APIRouter(prefix="/platform", tags=["Platform"])

# The only permission this entire router ever checks. No route below
# depends on get_current_company_id anywhere - a System Administrator has
# no company_id at all (see get_current_company_id's own docstring), and
# every route here exists specifically to see across every company, not
# one. A company_id appearing in a URL below identifies the resource being
# inspected, never authorization - access comes exclusively from this role
# check, identical for every company_id a caller might supply.
_PLATFORM_ROLES = ("System Administrator",)


@router.get("/overview", response_model=DataResponse[PlatformOverviewResponse])
def get_platform_overview(
    platform_service: PlatformService = Depends(get_platform_service),
    _current_user: User = Depends(require_roles(*_PLATFORM_ROLES)),
) -> DataResponse[PlatformOverviewResponse]:
    overview = platform_service.get_overview()
    return DataResponse(
        data=PlatformOverviewResponse.from_domain(overview),
        msg="Platform overview fetched successfully",
    )


@router.get("/companies", response_model=DataResponse[list[CompanySummaryResponse]])
def list_platform_companies(
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    platform_service: PlatformService = Depends(get_platform_service),
    _current_user: User = Depends(require_roles(*_PLATFORM_ROLES)),
) -> DataResponse[list[CompanySummaryResponse]]:
    companies, total = platform_service.list_companies(
        search=search,
        is_active=is_active,
        sort_by=sort_by,
        sort_dir=sort_dir,
        skip=skip,
        limit=limit,
    )
    return DataResponse(
        data=[CompanySummaryResponse.model_validate(c) for c in companies],
        msg=f"Fetched {len(companies)} of {total} companies",
    )


@router.get("/companies/{company_id}", response_model=DataResponse[CompanyDetailResponse])
def get_platform_company_detail(
    company_id: int,
    platform_service: PlatformService = Depends(get_platform_service),
    _current_user: User = Depends(require_roles(*_PLATFORM_ROLES)),
) -> DataResponse[CompanyDetailResponse]:
    try:
        detail = platform_service.get_company_detail(company_id)
    except CompanyNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found") from exc
    return DataResponse(
        data=CompanyDetailResponse.from_domain(detail),
        msg="Company detail fetched successfully",
    )
