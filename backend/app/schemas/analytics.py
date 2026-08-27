from pydantic import BaseModel

from app.models.enums import TERMINAL_TICKET_STATUSES, InventoryStatus, TicketStatus
from app.services.analytics_service import InventoryAnalytics, TicketAnalytics


class StatusBreakdownItem(BaseModel):
    status: TicketStatus
    count: int


class PriorityBreakdownItem(BaseModel):
    priority: str
    count: int


class CategoryBreakdownItem(BaseModel):
    category: str
    count: int


class MonthlyTrendItem(BaseModel):
    month: str
    created: int
    resolved: int


class TicketAnalyticsResponse(BaseModel):
    """GET /analytics/tickets - already scoped to exactly what the caller
    is allowed to see before this schema ever sees it (see
    AnalyticsService.get_ticket_analytics / TicketService.resolve_ownership_scope) -
    this class only reshapes that result for the wire, it makes no scoping
    decisions of its own.

    unassigned_count is null for Technician/Employee - "unassigned" has no
    scoped-to-me meaning for them, so AnalyticsService never computes it at
    all for those roles (not just hides it here).
    """

    open_count: int
    in_progress_count: int
    waiting_for_employee_count: int
    high_priority_open_count: int
    unassigned_count: int | None
    created_today: int
    resolved_today: int
    avg_resolution_minutes: float | None
    by_status: list[StatusBreakdownItem]
    by_priority: list[PriorityBreakdownItem]
    by_category: list[CategoryBreakdownItem]
    monthly_trend: list[MonthlyTrendItem]

    @classmethod
    def from_domain(cls, analytics: TicketAnalytics) -> "TicketAnalyticsResponse":
        """The only place TicketAnalytics's raw by_status dict is turned
        into the three named counts (open/in_progress/waiting) the
        frontend wants directly - derived from data AnalyticsService
        already computed via one GROUP BY query, not a new aggregate."""
        open_count = sum(
            count
            for status, count in analytics.by_status.items()
            if status not in TERMINAL_TICKET_STATUSES
        )
        return cls(
            open_count=open_count,
            in_progress_count=analytics.by_status.get(TicketStatus.IN_PROGRESS, 0),
            waiting_for_employee_count=analytics.by_status.get(
                TicketStatus.WAITING_FOR_EMPLOYEE, 0
            ),
            high_priority_open_count=analytics.high_priority_open_count,
            unassigned_count=analytics.unassigned_count,
            created_today=analytics.created_today_count,
            resolved_today=analytics.resolved_today_count,
            avg_resolution_minutes=analytics.avg_resolution_minutes,
            by_status=[
                StatusBreakdownItem(status=status, count=count)
                for status, count in analytics.by_status.items()
            ],
            by_priority=[
                PriorityBreakdownItem(priority=title, count=count)
                for title, count in analytics.by_priority
            ],
            by_category=[
                CategoryBreakdownItem(category=name, count=count)
                for name, count in analytics.by_category
            ],
            monthly_trend=[
                MonthlyTrendItem(
                    month=point.month_label,
                    created=point.created_count,
                    resolved=point.resolved_count,
                )
                for point in analytics.monthly_trend
            ],
        )


class InventoryStatusBreakdownItem(BaseModel):
    status: InventoryStatus
    count: int


class InventoryCategoryBreakdownItem(BaseModel):
    category: str
    count: int


class InventoryAnalyticsResponse(BaseModel):
    """GET /analytics/inventory - one schema for both roles it applies to
    (Employee is refused before this schema is ever built - see
    InventoryAnalyticsPermissionError). Company Administrator gets every
    company-wide field populated and reserved_for_my_tickets_count null
    (no meaningful company-wide equivalent); Technician gets the reverse -
    every company-wide field null and reserved_for_my_tickets_count
    populated. AnalyticsService.get_inventory_analytics decides which
    shape to build, not this class - from_domain only reshapes whatever
    InventoryAnalytics it's given.
    """

    total_items: int | None
    low_stock_count: int | None
    warranty_expiring_count: int | None
    by_status: list[InventoryStatusBreakdownItem] | None
    by_category: list[InventoryCategoryBreakdownItem] | None
    reserved_for_my_tickets_count: int | None

    @classmethod
    def from_domain(cls, analytics: InventoryAnalytics) -> "InventoryAnalyticsResponse":
        return cls(
            total_items=analytics.total_items,
            low_stock_count=analytics.low_stock_count,
            warranty_expiring_count=analytics.warranty_expiring_count,
            by_status=(
                None
                if analytics.by_status is None
                else [
                    InventoryStatusBreakdownItem(status=status, count=count)
                    for status, count in analytics.by_status.items()
                ]
            ),
            by_category=(
                None
                if analytics.by_category is None
                else [
                    InventoryCategoryBreakdownItem(category=name, count=count)
                    for name, count in analytics.by_category
                ]
            ),
            reserved_for_my_tickets_count=analytics.reserved_for_my_tickets_count,
        )
