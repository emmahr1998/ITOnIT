from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.time import local_day_boundaries_utc, local_month_boundaries_utc
from app.models.enums import InventoryStatus, TicketStatus
from app.models.user import User
from app.repositories.inventory_item import InventoryItemRepository
from app.repositories.ticket import TicketRepository
from app.repositories.ticket_inventory_usage import TicketInventoryUsageRepository
from app.services.ticket_service import TECHNICIAN_ROLE_NAME, TicketService

# "Last 6 calendar months including the current month" - fixed per the
# approved Phase A design; not currently configurable.
_TREND_MONTHS = 6

_COMPANY_ADMINISTRATOR_ROLE_NAME = "Company Administrator"
# Employee is deliberately absent - it has no valid inventory-analytics
# view at all (matches Employee having no inventory access anywhere else
# in this codebase - see inventory_items.py's own _VIEW_ROLES).
_INVENTORY_ANALYTICS_ROLES = (TECHNICIAN_ROLE_NAME, _COMPANY_ADMINISTRATOR_ROLE_NAME)

# Matches the frontend's own warranty-expiring threshold
# (frontend/src/utils/inventoryStatus.ts's WARRANTY_WARNING_DAYS).
_WARRANTY_EXPIRING_WINDOW_DAYS = 30


class InventoryAnalyticsPermissionError(Exception):
    """Raised when get_inventory_analytics is called for a role with no
    valid inventory-analytics view (Employee, or anything else). The
    route already gates this via require_roles - this exception exists
    so the service itself never assumes an ungated caller's role is
    valid and silently returns an empty/wrong response instead of
    refusing outright."""

    def __init__(self, role_name: str) -> None:
        super().__init__(f"Role {role_name!r} has no inventory analytics view")
        self.role_name = role_name


@dataclass(frozen=True)
class MonthlyTrendPoint:
    month_label: str
    created_count: int
    resolved_count: int


@dataclass(frozen=True)
class TicketAnalytics:
    """Ticket analytics foundation for one caller, already scoped to
    exactly what they're allowed to see (TicketService.resolve_ownership_scope).
    No API schema wraps this yet - Phase A is the repository/service
    layer only; a route/response-schema pair is a later, separate phase.
    """

    by_status: dict[TicketStatus, int]
    by_priority: list[tuple[str, int]]
    by_category: list[tuple[str, int]]
    high_priority_open_count: int
    # None unless the caller is a Company Administrator - "unassigned"
    # has no meaningful scoped-to-me interpretation for Technician/Employee,
    # so it is never computed for them, not just hidden after the fact.
    unassigned_count: int | None
    created_today_count: int
    resolved_today_count: int
    # None when there are zero resolved tickets in scope - "no data", not
    # "resolved instantly". Secondary metric only - no SLA/first-response
    # concept exists in this schema.
    avg_resolution_minutes: float | None
    monthly_trend: list[MonthlyTrendPoint]


@dataclass(frozen=True)
class InventoryAnalytics:
    """Inventory analytics for one caller. Company Administrator gets the
    full company-wide picture; Technician gets only
    reserved_for_my_tickets_count, with every company-wide field left
    None - a Technician response is never "the admin shape with some
    fields hidden downstream," it is a genuinely different, narrower
    result assembled by a different branch of
    AnalyticsService.get_inventory_analytics.
    """

    total_items: int | None
    low_stock_count: int | None
    warranty_expiring_count: int | None
    by_status: dict[InventoryStatus, int] | None
    by_category: list[tuple[str, int]] | None
    # Count of currently-RESERVED usage rows (reserved item *lines*) on
    # tickets assigned to this technician - not total reserved quantity.
    # A BULK reservation of 5 units and a SERIALIZED reservation of 1 unit
    # each count as 1 here ("one thing I have reserved for a ticket"),
    # which is the more directly actionable number for a technician than
    # a quantity sum mixing units across item types. A documented choice,
    # not the only defensible one - see the Phase C report. None for
    # Company Administrator - "my tickets" has no meaningful company-wide
    # equivalent (matches TicketAnalytics.unassigned_count's precedent of
    # some fields only existing for one role).
    reserved_for_my_tickets_count: int | None


class AnalyticsService:
    """Read-only ticket-analytics aggregation. Owns no table of its own -
    composes TicketRepository's aggregate queries with the one canonical
    ownership rule from TicketService, so analytics and normal ticket
    listing can never see a different set of tickets for the same user.

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), same convention as
    every other service in this codebase - never accepted from a client.
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        ticket_repository: TicketRepository | None = None,
        inventory_item_repository: InventoryItemRepository | None = None,
        ticket_inventory_usage_repository: TicketInventoryUsageRepository | None = None,
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._ticket_repository = (
            ticket_repository if ticket_repository is not None else TicketRepository(db, company_id)
        )
        self._inventory_item_repository = (
            inventory_item_repository
            if inventory_item_repository is not None
            else InventoryItemRepository(db, company_id)
        )
        self._ticket_inventory_usage_repository = (
            ticket_inventory_usage_repository
            if ticket_inventory_usage_repository is not None
            else TicketInventoryUsageRepository(db, company_id)
        )

    def get_ticket_analytics(
        self, current_user: User, *, now: datetime | None = None
    ) -> TicketAnalytics:
        """`now` is only ever supplied by tests, to make "today"/"this
        month" deterministic - production callers never pass it, and
        every date boundary below falls back to the real current instant.
        """
        scope = TicketService.resolve_ownership_scope(current_user)
        created_by = scope.created_by_user_id
        assigned_to = scope.assigned_technician_id

        by_status = self._ticket_repository.count_grouped_by_status(
            created_by_user_id=created_by, assigned_technician_id=assigned_to
        )
        by_priority = self._ticket_repository.count_grouped_by_priority(
            created_by_user_id=created_by, assigned_technician_id=assigned_to
        )
        by_category = self._ticket_repository.count_grouped_by_category(
            created_by_user_id=created_by, assigned_technician_id=assigned_to
        )
        high_priority_open_count = self._ticket_repository.count_high_priority_open(
            created_by_user_id=created_by, assigned_technician_id=assigned_to
        )
        # Company-wide only, and only ever computed for a Company
        # Administrator - see TicketRepository.count_unassigned's docstring.
        unassigned_count = self._ticket_repository.count_unassigned() if scope.is_company_wide else None
        avg_resolution_minutes = self._ticket_repository.avg_resolution_minutes(
            created_by_user_id=created_by, assigned_technician_id=assigned_to
        )

        # Company.timezone backs every date-boundary metric below:
        # local calendar boundary -> convert to UTC -> compare against
        # UTC-basis created_at/resolved_at. current_user.company is
        # already eager-loaded by UserRepository.get_by_id (see
        # get_current_active_user's docstring), so no extra query is
        # needed to read it.
        timezone_name = current_user.company.timezone

        today_start, today_end = local_day_boundaries_utc(timezone_name, now=now)
        (created_today_count,) = self._ticket_repository.count_created_by_boundaries(
            [(today_start, today_end)],
            created_by_user_id=created_by,
            assigned_technician_id=assigned_to,
        )
        (resolved_today_count,) = self._ticket_repository.count_resolved_by_boundaries(
            [(today_start, today_end)],
            created_by_user_id=created_by,
            assigned_technician_id=assigned_to,
        )

        month_boundaries = local_month_boundaries_utc(timezone_name, _TREND_MONTHS, now=now)
        month_ranges = [(start, end) for _, start, end in month_boundaries]
        created_counts = self._ticket_repository.count_created_by_boundaries(
            month_ranges, created_by_user_id=created_by, assigned_technician_id=assigned_to
        )
        resolved_counts = self._ticket_repository.count_resolved_by_boundaries(
            month_ranges, created_by_user_id=created_by, assigned_technician_id=assigned_to
        )
        monthly_trend = [
            MonthlyTrendPoint(month_label=label, created_count=created, resolved_count=resolved)
            for (label, _, _), created, resolved in zip(
                month_boundaries, created_counts, resolved_counts
            )
        ]

        return TicketAnalytics(
            by_status=by_status,
            by_priority=by_priority,
            by_category=by_category,
            high_priority_open_count=high_priority_open_count,
            unassigned_count=unassigned_count,
            created_today_count=created_today_count,
            resolved_today_count=resolved_today_count,
            avg_resolution_minutes=avg_resolution_minutes,
            monthly_trend=monthly_trend,
        )

    def get_inventory_analytics(self, current_user: User) -> InventoryAnalytics:
        """Company Administrator gets the full company-wide picture,
        computed entirely via SQL aggregates (InventoryItemRepository's
        existing count_with_filters for total/low-stock/warranty-expiring,
        reused unchanged rather than duplicated, plus its two new
        GROUP BY methods for the breakdowns). Technician gets only
        reserved_for_my_tickets_count - never the company-wide dataset,
        even though the frontend could simply choose not to render it;
        the narrower response is assembled here, not filtered downstream.
        Employee (and any other role) is refused outright - see
        InventoryAnalyticsPermissionError.
        """
        role_name = current_user.role.name
        if role_name not in _INVENTORY_ANALYTICS_ROLES:
            raise InventoryAnalyticsPermissionError(role_name)

        if role_name == _COMPANY_ADMINISTRATOR_ROLE_NAME:
            return InventoryAnalytics(
                total_items=self._inventory_item_repository.count_with_filters(),
                low_stock_count=self._inventory_item_repository.count_with_filters(low_stock=True),
                warranty_expiring_count=self._inventory_item_repository.count_with_filters(
                    warranty_expiring_days=_WARRANTY_EXPIRING_WINDOW_DAYS
                ),
                by_status=self._inventory_item_repository.count_grouped_by_status(),
                by_category=self._inventory_item_repository.count_grouped_by_category(),
                reserved_for_my_tickets_count=None,
            )

        # Technician.
        return InventoryAnalytics(
            total_items=None,
            low_stock_count=None,
            warranty_expiring_count=None,
            by_status=None,
            by_category=None,
            reserved_for_my_tickets_count=(
                self._ticket_inventory_usage_repository.count_reserved_for_technician(current_user.id)
            ),
        )
