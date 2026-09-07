from pydantic import BaseModel, ConfigDict

from app.schemas.types import UTCDatetime
from app.services.platform_service import CompanyDetail, PlatformOverview


class PlatformLoginRequest(BaseModel):
    """POST /platform/login request body (Milestone 8, Phase 8.3).

    Deliberately has no company_code field - this resolves the one
    platform-level System Administrator account (company_id IS NULL), not
    a tenant user, so there is no company to identify. ``username`` is
    kept as the field name for consistency with the tenant LoginRequest
    (backend/app/schemas/auth.py) - it matches either the username or
    email column, same convention as that schema.
    """

    username: str
    password: str


class CompanySummaryResponse(BaseModel):
    """One row of GET /platform/companies, and the shape
    GET /platform/overview's recent_companies uses - deliberately smaller
    than CompanyDetailResponse (no aggregate counts, which would mean an
    extra query per row for a list of many companies - see
    PlatformService.list_companies, which never computes per-company counts
    for a list view, only get_company_detail does, for exactly one company).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    company_code: str
    is_active: bool
    contact_email: str | None
    timezone: str
    language: str
    created_at: UTCDatetime


class PlatformOverviewResponse(BaseModel):
    """GET /platform/overview. total_users is tenant users only
    (company_id IS NOT NULL) - the System Administrator's own account is
    deliberately never counted here, see
    UserRepository.count_all_tenant_users."""

    total_companies: int
    active_companies: int
    inactive_companies: int
    total_users: int
    recent_companies: list[CompanySummaryResponse]

    @classmethod
    def from_domain(cls, overview: PlatformOverview) -> "PlatformOverviewResponse":
        return cls(
            total_companies=overview.total_companies,
            active_companies=overview.active_companies,
            inactive_companies=overview.inactive_companies,
            total_users=overview.total_users,
            recent_companies=[
                CompanySummaryResponse.model_validate(c) for c in overview.recent_companies
            ],
        )


class CompanyDetailResponse(BaseModel):
    """GET /platform/companies/{id}. user_count/ticket_count/
    inventory_item_count are always computed for this one target company -
    see PlatformService.get_company_detail's docstring on why the target id
    is never derived from the caller."""

    id: int
    name: str
    company_code: str
    is_active: bool
    contact_email: str | None
    timezone: str
    language: str
    created_at: UTCDatetime
    updated_at: UTCDatetime
    user_count: int
    ticket_count: int
    inventory_item_count: int

    @classmethod
    def from_domain(cls, detail: CompanyDetail) -> "CompanyDetailResponse":
        company = detail.company
        return cls(
            id=company.id,
            name=company.name,
            company_code=company.company_code,
            is_active=company.is_active,
            contact_email=company.contact_email,
            timezone=company.timezone,
            language=company.language,
            created_at=company.created_at,
            updated_at=company.updated_at,
            user_count=detail.user_count,
            ticket_count=detail.ticket_count,
            inventory_item_count=detail.inventory_item_count,
        )
