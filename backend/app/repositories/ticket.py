from datetime import datetime

from sqlalchemy import case, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.models.category import Category
from app.models.enums import TicketStatus
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.base import CompanyScopedRepository

_EAGER_OPTIONS = (
    selectinload(Ticket.category),
    selectinload(Ticket.priority),
    selectinload(Ticket.location),
    selectinload(Ticket.created_by),
    selectinload(Ticket.assigned_technician),
)

_SORTABLE_COLUMNS = {
    "created_at": Ticket.created_at,
    "updated_at": Ticket.updated_at,
    "title": Ticket.title,
    "ticket_number": Ticket.ticket_number,
}

# A ticket in one of these statuses is done - excluded from "open" counts
# like high/critical-open. Mirrors the frontend dashboard's own openStatuses
# set (frontend/src/pages/DashboardPage.tsx) so "open" means the same thing
# on both sides.
_TERMINAL_STATUSES = frozenset({TicketStatus.RESOLVED, TicketStatus.CLOSED})

# "High/Critical" is a business concept expressed as Priority.title text,
# not a hardcoded id - these are the exact seeded titles (see
# CompanyService._seed_defaults), matched case-sensitively against
# whatever a company's own priorities are actually named.
_HIGH_CRITICAL_PRIORITY_TITLES = ("High", "Critical")


class TicketRepository(CompanyScopedRepository[Ticket]):
    """Ticket persistence: filtered listing and ticket-number sequencing.
    Company-scoped - see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, Ticket, company_id)

    def get_by_id(self, id_: int) -> Ticket | None:
        """Overrides CompanyScopedRepository.get_by_id to additionally
        eager-load the relationships every TicketResponse needs, avoiding
        an N+1 query per nested field."""
        return self.db.scalar(
            select(Ticket)
            .where(Ticket.id == id_, Ticket.company_id == self.company_id)
            .options(*_EAGER_OPTIONS)
        )

    def get_with_filters(
        self,
        *,
        status: TicketStatus | None = None,
        priority_id: int | None = None,
        category_id: int | None = None,
        department_id: int | None = None,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        skip: int | None = None,
        limit: int | None = None,
    ) -> list[Ticket]:
        """One filter method covers every caller: Company Administrator's free
        filtering and Employee/Technician's forced ownership scope are both
        just filters.

        skip/limit default to None (no pagination applied) so the existing
        GET /tickets caller, which never passes them, keeps returning every
        matching row exactly as before; GET /all-tickets is the caller that
        supplies them.
        """
        stmt = (
            select(Ticket)
            .where(Ticket.company_id == self.company_id)
            .options(*_EAGER_OPTIONS)
        )
        if department_id is not None:
            stmt = stmt.join(User, Ticket.created_by_user_id == User.id).where(
                User.department_id == department_id
            )
        if status is not None:
            stmt = stmt.where(Ticket.status == status)
        if priority_id is not None:
            stmt = stmt.where(Ticket.priority_id == priority_id)
        if category_id is not None:
            stmt = stmt.where(Ticket.category_id == category_id)
        if created_by_user_id is not None:
            stmt = stmt.where(Ticket.created_by_user_id == created_by_user_id)
        if assigned_technician_id is not None:
            stmt = stmt.where(Ticket.assigned_technician_id == assigned_technician_id)
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Ticket.title).like(pattern),
                    func.lower(Ticket.description).like(pattern),
                )
            )

        sort_column = _SORTABLE_COLUMNS.get(sort_by, Ticket.created_at)
        stmt = stmt.order_by(sort_column.asc() if sort_dir == "asc" else sort_column.desc())

        if skip is not None:
            stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).all())

    def count_for_year(self, year: int) -> int:
        """Used to generate the next sequential ticket_number for a given
        year - scoped to the caller's own company, since each company's
        ticket numbering starts from 000001 independently (matching
        ticket_number's new per-company uniqueness)."""
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Ticket)
                .where(
                    Ticket.ticket_number.like(f"IT-{year}-%"),
                    Ticket.company_id == self.company_id,
                )
            )
            or 0
        )

    # ---- analytics aggregates --------------------------------------------
    #
    # Every method below takes the same optional (created_by_user_id,
    # assigned_technician_id) pair TicketService.resolve_ownership_scope
    # produces - the identical role-scoping rule normal ticket listing
    # uses, applied inside the aggregate query itself rather than computed
    # company-wide and filtered afterward. All are SQL COUNT/GROUP BY/AVG -
    # no full Ticket row is ever fetched for these.

    def _scope_filters(
        self, created_by_user_id: int | None, assigned_technician_id: int | None
    ) -> list:
        filters = [Ticket.company_id == self.company_id]
        if created_by_user_id is not None:
            filters.append(Ticket.created_by_user_id == created_by_user_id)
        if assigned_technician_id is not None:
            filters.append(Ticket.assigned_technician_id == assigned_technician_id)
        return filters

    def count_grouped_by_status(
        self,
        *,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> dict[TicketStatus, int]:
        """One GROUP BY query for the whole status breakdown - never one
        COUNT per status. A status with zero matching tickets simply
        doesn't appear in the result (matches the frontend's own sparse
        breakdown rendering)."""
        stmt = (
            select(Ticket.status, func.count())
            .where(*self._scope_filters(created_by_user_id, assigned_technician_id))
            .group_by(Ticket.status)
        )
        return dict(self.db.execute(stmt).all())

    def count_grouped_by_priority(
        self,
        *,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> list[tuple[str, int]]:
        """One GROUP BY query, joined to Priority for its title so the
        result is directly displayable with no second lookup. The
        Priority.company_id predicate is redundant in practice (a
        ticket's priority_id can only ever point to a priority in the
        same company - enforced at write time) but kept explicit anyway,
        matching CompanyScopedRepository's own documented convention of
        never relying on a join alone for isolation."""
        stmt = (
            select(Priority.title, func.count())
            .select_from(Ticket)
            .join(Priority, Ticket.priority_id == Priority.id)
            .where(
                *self._scope_filters(created_by_user_id, assigned_technician_id),
                Priority.company_id == self.company_id,
            )
            .group_by(Priority.title)
        )
        return list(self.db.execute(stmt).all())

    def count_grouped_by_category(
        self,
        *,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> list[tuple[str, int]]:
        """Same shape and same isolation rationale as count_grouped_by_priority."""
        stmt = (
            select(Category.name, func.count())
            .select_from(Ticket)
            .join(Category, Ticket.category_id == Category.id)
            .where(
                *self._scope_filters(created_by_user_id, assigned_technician_id),
                Category.company_id == self.company_id,
            )
            .group_by(Category.name)
        )
        return list(self.db.execute(stmt).all())

    def count_high_priority_open(
        self,
        *,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> int:
        """"High/Critical open" = priority title in ('High', 'Critical')
        AND status not in the terminal set - both business concepts
        (_HIGH_CRITICAL_PRIORITY_TITLES, _TERMINAL_STATUSES), never a
        hardcoded id."""
        stmt = (
            select(func.count())
            .select_from(Ticket)
            .join(Priority, Ticket.priority_id == Priority.id)
            .where(
                *self._scope_filters(created_by_user_id, assigned_technician_id),
                Priority.company_id == self.company_id,
                Priority.title.in_(_HIGH_CRITICAL_PRIORITY_TITLES),
                Ticket.status.notin_(_TERMINAL_STATUSES),
            )
        )
        return self.db.scalar(stmt) or 0

    def count_unassigned(self) -> int:
        """Unassigned = status NEW with no technician assigned yet -
        matches the existing dashboard's own "Pending Assignments"
        definition (frontend/src/pages/DashboardPage.tsx). Company-wide
        only, deliberately no ownership-scope parameters: "unassigned"
        isn't a meaningful concept scoped to one technician's or one
        employee's own tickets, so this is only ever called for a
        Company Administrator (TicketOwnershipScope.is_company_wide) -
        the caller decides whether to call it at all, not this method.
        """
        stmt = (
            select(func.count())
            .select_from(Ticket)
            .where(
                Ticket.company_id == self.company_id,
                Ticket.status == TicketStatus.NEW,
                Ticket.assigned_technician_id.is_(None),
            )
        )
        return self.db.scalar(stmt) or 0

    def avg_resolution_minutes(
        self,
        *,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> float | None:
        """AVG(DATEDIFF(minute, created_at, resolved_at)) over resolved
        tickets only. Valid now that both columns share the same UTC
        basis (see docs/TECH_DEBT.md's UTC timestamp normalization entry)
        - this query would have been silently wrong by the DB server's
        UTC offset before that fix landed. `minute` must go through
        text() rather than a bound parameter/string literal - DATEDIFF's
        first argument is a T-SQL keyword, not a value. None (not 0) when
        there are zero resolved tickets - "no data" is not "instant
        resolution".
        """
        stmt = select(
            func.avg(func.datediff(text("minute"), Ticket.created_at, Ticket.resolved_at))
        ).where(
            *self._scope_filters(created_by_user_id, assigned_technician_id),
            Ticket.resolved_at.is_not(None),
        )
        result = self.db.scalar(stmt)
        return float(result) if result is not None else None

    def count_created_by_boundaries(
        self,
        boundaries: list[tuple[datetime, datetime]],
        *,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> list[int]:
        """One COUNT per [start, end) boundary pair, via one GROUP BY
        query with a CASE bucket expression - not one query per boundary.
        Used for both "created today" (a single-pair list) and the
        monthly trend's created series (a multi-pair list) - the boundary
        pairs themselves (company-local calendar days/months, converted
        to UTC) are computed by the caller; this method only counts
        against them. Always returns exactly len(boundaries) integers, in
        the given order, 0 for any boundary with no matching tickets -
        a bucket never silently disappears from the result.
        """
        return self._count_by_boundaries(Ticket.created_at, boundaries, created_by_user_id, assigned_technician_id)

    def count_resolved_by_boundaries(
        self,
        boundaries: list[tuple[datetime, datetime]],
        *,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> list[int]:
        """Same as count_created_by_boundaries, bucketed on resolved_at
        instead - a NULL resolved_at can never match any boundary, so
        unresolved tickets are naturally excluded with no extra predicate.
        """
        return self._count_by_boundaries(Ticket.resolved_at, boundaries, created_by_user_id, assigned_technician_id)

    def _count_by_boundaries(
        self,
        date_column,
        boundaries: list[tuple[datetime, datetime]],
        created_by_user_id: int | None,
        assigned_technician_id: int | None,
    ) -> list[int]:
        if not boundaries:
            return []

        bucket = case(
            *(
                ((date_column >= start) & (date_column < end), i)
                for i, (start, end) in enumerate(boundaries)
            ),
            else_=None,
        ).label("bucket")

        # Materialize the CASE as a real column of a derived table before
        # grouping by it, rather than repeating the CASE expression in both
        # SELECT and GROUP BY - confirmed against the real SQL Server that
        # the repeated-expression form fails ("column is invalid in the
        # select list because it is not contained in ... the GROUP BY
        # clause"), because each occurrence of the CASE gets its own set of
        # bound parameters and SQL Server does not treat the two
        # independently-parameterized copies as the same expression for
        # GROUP BY matching. Grouping by a derived table's own column name
        # has no such ambiguity.
        inner = (
            select(bucket)
            .where(*self._scope_filters(created_by_user_id, assigned_technician_id))
            .subquery()
        )
        stmt = select(inner.c.bucket, func.count()).group_by(inner.c.bucket)

        counts = [0] * len(boundaries)
        for bucket_index, count in self.db.execute(stmt).all():
            if bucket_index is not None:
                counts[bucket_index] = count
        return counts
