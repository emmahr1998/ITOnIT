from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories.base import BaseRepository

# Platform admin list/sort allowlist (Milestone 8, Phase 8.1) - sort_by is
# looked up here, never interpolated as a raw column name. An unrecognized
# value silently falls back to created_at, the same convention
# TicketRepository's own _SORTABLE_COLUMNS lookup uses.
_SORTABLE_COLUMNS = {
    "created_at": Company.created_at,
    "name": Company.name,
    "company_code": Company.company_code,
}


class CompanyRepository(BaseRepository[Company]):
    """Company lookups needed for authentication, plus the platform-admin
    read surface (Milestone 8, Phase 8.1).

    Deliberately NOT built on CompanyScopedRepository: a company is the
    tenant boundary itself, not tenant-owned data - same reasoning as
    RoleRepository staying unscoped. This is also the one repository in the
    codebase that is *supposed* to see across every tenant at once -
    get_with_filters/count_with_filters below are the platform's own
    cross-company listing, used only by PlatformService (System
    Administrator only), never by any tenant-scoped route.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db, Company)

    def get_by_code(self, company_code: str) -> Company | None:
        """Case-insensitive lookup, since a company code is typed by hand."""
        return self.db.scalar(
            select(Company).where(
                func.lower(Company.company_code) == company_code.strip().lower()
            )
        )

    def _filtered_statement(self, *, search: str | None, is_active: bool | None):
        stmt = select(Company)
        if is_active is not None:
            stmt = stmt.where(Company.is_active == is_active)
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Company.name).like(pattern),
                    func.lower(Company.company_code).like(pattern),
                )
            )
        return stmt

    def get_with_filters(
        self,
        *,
        search: str | None = None,
        is_active: bool | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> list[Company]:
        """Every tenant company, optionally filtered by a name/company_code
        search and active status - mirrors UserRepository.get_with_filters's
        shape exactly. Used both by GET /platform/companies and, with a
        fixed sort/limit, by GET /platform/overview's recent_companies."""
        stmt = self._filtered_statement(search=search, is_active=is_active)
        sort_column = _SORTABLE_COLUMNS.get(sort_by, Company.created_at)
        stmt = stmt.order_by(sort_column.asc() if sort_dir == "asc" else sort_column.desc())
        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def count_with_filters(
        self, *, search: str | None = None, is_active: bool | None = None
    ) -> int:
        """Total matching rows for the same filters as get_with_filters,
        ignoring skip/limit - also how PlatformService.get_overview computes
        total/active/inactive company counts (is_active=None/True/False)."""
        stmt = self._filtered_statement(search=search, is_active=is_active)
        return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
