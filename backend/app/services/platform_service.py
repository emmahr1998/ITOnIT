from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories.company import CompanyRepository
from app.repositories.inventory_item import InventoryItemRepository
from app.repositories.ticket import TicketRepository
from app.repositories.user import UserRepository
from app.schemas.company import CompanyRegisterRequest
from app.services.company_service import CompanyService

# Small, fixed - not a query parameter. GET /platform/overview shows a
# glance, not a full list (that's what GET /platform/companies is for).
_RECENT_COMPANIES_LIMIT = 5


class CompanyNotFoundError(Exception):
    """Raised when a platform-admin company_id does not exist.

    Deliberately a separate exception from CompanyService's own
    CompanyNotFoundError - get_company_detail below never calls
    CompanyService, only CompanyRepository directly, so this stays this
    module's own domain exception. create_company (Phase 8.4) does call
    CompanyService.register_company, but deliberately lets that method's
    own CompanyCodeConflictError propagate unchanged rather than wrapping
    it in a second, redundant exception type - see create_company's
    docstring.
    """


@dataclass(frozen=True)
class PlatformOverview:
    """GET /platform/overview's domain result. recent_companies is a plain
    list of Company ORM rows - PlatformOverviewResponse.from_domain reshapes
    them into CompanySummaryResponse for the wire, same separation of
    concerns as every other *_service.py in this codebase."""

    total_companies: int
    active_companies: int
    inactive_companies: int
    total_users: int
    recent_companies: list[Company]


@dataclass(frozen=True)
class CompanyDetail:
    """GET /platform/companies/{id}'s domain result: the company row plus
    three aggregate counts, each computed for that one target company only."""

    company: Company
    user_count: int
    ticket_count: int
    inventory_item_count: int


class PlatformService:
    """Platform-level orchestration for the System Administrator console:
    GET /platform/overview, GET /platform/companies,
    GET /platform/companies/{id} (Phase 8.1), PATCH .../activate|deactivate
    (Phase 8.2), and POST /platform/companies (Phase 8.4).

    Deliberately separate from CompanyService, which owns tenant/company
    lifecycle *business logic* (registration, settings, logo) - a System
    Administrator's view across every company is a fundamentally different
    kind of operation from a Company Administrator managing its own company,
    not a superset of it. This service does not reimplement any of that
    business logic; create_company below delegates the entire job to
    CompanyService.register_company unchanged, exactly like every read
    method here delegates its counting to the repository layer rather than
    recomputing anything by hand. This service is never given a company_id
    at construction time, unlike every tenant-scoped service in this
    codebase - it has no "caller's own company" to be scoped to at all.
    Every repository it uses for a *target* company's aggregate counts is
    constructed explicitly with that company's own id, taken from the
    method argument the route passed straight from the URL (or, for
    create_company, from CompanyService.register_company's own return
    value) - never derived from the caller (a System Administrator has no
    company_id - see get_current_company_id's docstring) and never treated
    as authorization (that's require_roles("System Administrator") alone,
    enforced by the route, before this service is ever called).
    """

    def __init__(
        self,
        db: Session,
        company_repository: CompanyRepository | None = None,
        platform_user_repository: UserRepository | None = None,
        user_repository_factory: Callable[[int], UserRepository] | None = None,
        ticket_repository_factory: Callable[[int], TicketRepository] | None = None,
        inventory_item_repository_factory: (
            Callable[[int], InventoryItemRepository] | None
        ) = None,
        company_service: CompanyService | None = None,
    ) -> None:
        self._db = db
        self._company_repository = company_repository or CompanyRepository(db)
        # Unscoped by construction (company_id=None) - the one legitimate
        # cross-tenant User query in this codebase, used only for
        # get_overview's total_users. Never used to look up or authenticate
        # any individual user.
        self._platform_user_repository = platform_user_repository or UserRepository(db)
        self._user_repository_factory = user_repository_factory or (
            lambda company_id: UserRepository(db, company_id)
        )
        self._ticket_repository_factory = ticket_repository_factory or (
            lambda company_id: TicketRepository(db, company_id)
        )
        self._inventory_item_repository_factory = inventory_item_repository_factory or (
            lambda company_id: InventoryItemRepository(db, company_id)
        )
        self._company_service = company_service or CompanyService(db)

    def get_overview(self) -> PlatformOverview:
        return PlatformOverview(
            total_companies=self._company_repository.count_with_filters(),
            active_companies=self._company_repository.count_with_filters(is_active=True),
            inactive_companies=self._company_repository.count_with_filters(is_active=False),
            total_users=self._platform_user_repository.count_all_tenant_users(),
            recent_companies=self._company_repository.get_with_filters(
                sort_by="created_at", sort_dir="desc", limit=_RECENT_COMPANIES_LIMIT
            ),
        )

    def list_companies(
        self,
        *,
        search: str | None = None,
        is_active: bool | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Company], int]:
        companies = self._company_repository.get_with_filters(
            search=search,
            is_active=is_active,
            sort_by=sort_by,
            sort_dir=sort_dir,
            skip=skip,
            limit=limit,
        )
        total = self._company_repository.count_with_filters(search=search, is_active=is_active)
        return companies, total

    def get_company_detail(self, company_id: int) -> CompanyDetail:
        company = self._company_repository.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError
        return CompanyDetail(
            company=company,
            user_count=self._user_repository_factory(company_id).count_with_filters(),
            ticket_count=self._ticket_repository_factory(company_id).count_total(),
            inventory_item_count=(
                self._inventory_item_repository_factory(company_id).count_with_filters()
            ),
        )

    def set_company_active(self, company_id: int, is_active: bool) -> CompanyDetail:
        """Phase 8.2: the only mutation this service performs, and the only
        one it ever will for company lifecycle - flips is_active and
        nothing else. Idempotent by construction: writing the same value a
        company already has still succeeds and still returns a fresh
        CompanyDetail, since a boolean column has no "already in that
        state" error to raise. Every access-control consequence of this
        flip (blocking company resolution/login, blocking every
        already-authenticated request via get_current_active_user) is
        enforced entirely by existing auth code this method never touches -
        see AuthService.resolve_company/authenticate and
        get_current_active_user's own docstrings. This method does not
        cascade to users/tickets/inventory/settings in any way; reuses
        get_company_detail for the response rather than duplicating its
        aggregate-count queries."""
        company = self._company_repository.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError
        company.is_active = is_active
        self._company_repository.update(company)
        self._db.commit()
        return self.get_company_detail(company_id)

    def create_company(self, payload: CompanyRegisterRequest) -> CompanyDetail:
        """Phase 8.4: a System Administrator provisioning a tenant company
        on a customer's behalf. Delegates the entire job - company-code
        uniqueness check, company + first Company Administrator + all
        starter data, one atomic transaction - to
        CompanyService.register_company unchanged; this method adds no
        business logic of its own beyond obtaining the response. Deliberately
        does not catch CompanyCodeConflictError here: it propagates
        unchanged up to the route, which maps it exactly the same way
        POST /companies/register's own route already does - one exception
        type, one 409 mapping, not a second platform-specific copy of
        either. Unlike self-registration, the caller (a System
        Administrator) is never issued tokens for the new tenant admin -
        see the route's own docstring."""
        admin = self._company_service.register_company(payload)
        return self.get_company_detail(admin.company_id)
