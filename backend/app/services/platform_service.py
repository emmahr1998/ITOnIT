from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories.company import CompanyRepository
from app.repositories.inventory_item import InventoryItemRepository
from app.repositories.ticket import TicketRepository
from app.repositories.user import UserRepository

# Small, fixed - not a query parameter. GET /platform/overview shows a
# glance, not a full list (that's what GET /platform/companies is for).
_RECENT_COMPANIES_LIMIT = 5


class CompanyNotFoundError(Exception):
    """Raised when a platform-admin company_id does not exist.

    Deliberately a separate exception from CompanyService's own
    CompanyNotFoundError - this service does not import from CompanyService
    at all (see this module's own docstring on why platform orchestration
    and tenant/company lifecycle business logic stay in separate services).
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
    """Read-only platform-level orchestration for the System Administrator
    console (Milestone 8, Phase 8.1: GET /platform/overview,
    GET /platform/companies, GET /platform/companies/{id}).

    Deliberately separate from CompanyService, which owns tenant/company
    lifecycle business logic (registration, settings, logo) - a System
    Administrator's view across every company is a fundamentally different
    kind of operation from a Company Administrator managing its own company,
    not a superset of it. This service is never given a company_id at
    construction time, unlike every tenant-scoped service in this codebase -
    it has no "caller's own company" to be scoped to at all. Every
    repository it uses for a *target* company's aggregate counts is
    constructed explicitly with that company's own id, taken from the
    method argument the route passed straight from the URL - never derived
    from the caller (a System Administrator has no company_id - see
    get_current_company_id's docstring) and never treated as authorization
    (that's require_roles("System Administrator") alone, enforced by the
    route, before this service is ever called).
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
