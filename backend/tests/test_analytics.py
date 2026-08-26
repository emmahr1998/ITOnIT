"""Phase A: Ticket Analytics Foundation.

Tests AnalyticsService/TicketRepository's aggregate methods and the shared
TicketOwnershipScope directly (no HTTP layer exists yet - Phase A is
repository/service only, per the approved design). Uses the same
FakeTicketRepository convention as every other test file in this suite;
real-SQL-Server-specific behavior (DATEDIFF, GROUP BY, CASE bucketing) is
verified separately against the real dev database, not here - see the
Phase A report.
"""
from datetime import datetime, timezone

import pytest

from app.core.time import InvalidCompanyTimezoneError, local_day_boundaries_utc, local_month_boundaries_utc
from app.models.category import Category
from app.models.company import Company
from app.models.enums import TicketStatus
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.services.analytics_service import AnalyticsService
from app.services.ticket_service import TicketOwnershipScope, TicketService
from tests.conftest import COMPANY_A_ID, COMPANY_B_ID, FakeTicketRepository

# Fixed reference instant so "today"/"this month" are deterministic. All
# Company A fixtures below are dated relative to this, not real wall-clock
# time. Company A's timezone is "UTC" (see the company_a fixture), so local
# day/month boundaries reduce to plain UTC boundaries here - the dedicated
# non-UTC tests further down are what actually exercise the timezone-aware
# boundary math.
NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Company A ticket fixtures - six tickets, deliberately spanning several
# months, statuses, priorities, categories, creators, and assignees so every
# aggregate has genuine, non-trivial data to compute over.
# ---------------------------------------------------------------------------


@pytest.fixture
def t1_new_unassigned(active_employee_user, low_priority, hardware_category) -> Ticket:
    """Created today; NEW; unassigned; Low priority."""
    t = Ticket(
        id=1,
        company_id=COMPANY_A_ID,
        ticket_number="IT-2026-000001",
        title="T1",
        description="d",
        status=TicketStatus.NEW,
        priority_id=low_priority.id,
        category_id=hardware_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=None,
        created_at=datetime(2026, 8, 22, 8, 0, 0),
        updated_at=datetime(2026, 8, 22, 8, 0, 0),
    )
    t.priority = low_priority
    t.category = hardware_category
    t.created_by = active_employee_user
    t.assigned_technician = None
    return t


@pytest.fixture
def t2_assigned_high(
    active_employee_user, active_technician_user, high_priority, software_category
) -> Ticket:
    """Created this month (not today); ASSIGNED (open); High priority ->
    counts toward high_priority_open. Assigned to technician 1."""
    t = Ticket(
        id=2,
        company_id=COMPANY_A_ID,
        ticket_number="IT-2026-000002",
        title="T2",
        description="d",
        status=TicketStatus.ASSIGNED,
        priority_id=high_priority.id,
        category_id=software_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=active_technician_user.id,
        created_at=datetime(2026, 8, 20, 10, 0, 0),
        updated_at=datetime(2026, 8, 20, 10, 0, 0),
    )
    t.priority = high_priority
    t.category = software_category
    t.created_by = active_employee_user
    t.assigned_technician = active_technician_user
    return t


@pytest.fixture
def t3_in_progress_critical(
    active_employee_user_2, active_technician_user, critical_priority, hardware_category
) -> Ticket:
    """Created last month; IN_PROGRESS (open); Critical priority ->
    counts toward high_priority_open. Assigned to technician 1;
    created by employee 2."""
    t = Ticket(
        id=3,
        company_id=COMPANY_A_ID,
        ticket_number="IT-2026-000003",
        title="T3",
        description="d",
        status=TicketStatus.IN_PROGRESS,
        priority_id=critical_priority.id,
        category_id=hardware_category.id,
        created_by_user_id=active_employee_user_2.id,
        assigned_technician_id=active_technician_user.id,
        created_at=datetime(2026, 7, 15, 9, 0, 0),
        updated_at=datetime(2026, 7, 15, 9, 0, 0),
    )
    t.priority = critical_priority
    t.category = hardware_category
    t.created_by = active_employee_user_2
    t.assigned_technician = active_technician_user
    return t


@pytest.fixture
def t4_resolved_today(
    active_employee_user, active_technician_user_2, medium_priority, hardware_category
) -> Ticket:
    """Created yesterday, resolved today - a 1440-minute (24h) resolution,
    assigned to technician 2. RESOLVED is terminal, so this never counts
    toward high_priority_open regardless of priority."""
    t = Ticket(
        id=4,
        company_id=COMPANY_A_ID,
        ticket_number="IT-2026-000004",
        title="T4",
        description="d",
        status=TicketStatus.RESOLVED,
        priority_id=medium_priority.id,
        category_id=hardware_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=active_technician_user_2.id,
        created_at=datetime(2026, 8, 21, 9, 0, 0),
        updated_at=datetime(2026, 8, 22, 9, 0, 0),
        resolved_at=datetime(2026, 8, 22, 9, 0, 0),
    )
    t.priority = medium_priority
    t.category = hardware_category
    t.created_by = active_employee_user
    t.assigned_technician = active_technician_user_2
    return t


@pytest.fixture
def t5_closed_two_months_ago(
    active_employee_user_2, active_technician_user_2, critical_priority, software_category
) -> Ticket:
    """Created and resolved (also a 1440-minute resolution) two months
    before NOW, then closed. CLOSED is terminal - excluded from
    high_priority_open despite Critical priority. Assigned to technician 2;
    created by employee 2."""
    t = Ticket(
        id=5,
        company_id=COMPANY_A_ID,
        ticket_number="IT-2026-000005",
        title="T5",
        description="d",
        status=TicketStatus.CLOSED,
        priority_id=critical_priority.id,
        category_id=software_category.id,
        created_by_user_id=active_employee_user_2.id,
        assigned_technician_id=active_technician_user_2.id,
        created_at=datetime(2026, 6, 10, 9, 0, 0),
        updated_at=datetime(2026, 6, 12, 0, 0, 0),
        resolved_at=datetime(2026, 6, 11, 9, 0, 0),
        closed_at=datetime(2026, 6, 12, 0, 0, 0),
    )
    t.priority = critical_priority
    t.category = software_category
    t.created_by = active_employee_user_2
    t.assigned_technician = active_technician_user_2
    return t


@pytest.fixture
def t6_outside_trend_window(active_employee_user, low_priority, hardware_category) -> Ticket:
    """Created 8 months before NOW - outside the 6-month trend window
    (Mar-Aug 2026), but must still count in the non-date-scoped
    breakdowns (status/priority/category/high-open/unassigned)."""
    t = Ticket(
        id=6,
        company_id=COMPANY_A_ID,
        ticket_number="IT-2026-000006",
        title="T6",
        description="d",
        status=TicketStatus.NEW,
        priority_id=low_priority.id,
        category_id=hardware_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=None,
        created_at=datetime(2026, 1, 1, 9, 0, 0),
        updated_at=datetime(2026, 1, 1, 9, 0, 0),
    )
    t.priority = low_priority
    t.category = hardware_category
    t.created_by = active_employee_user
    t.assigned_technician = None
    return t


@pytest.fixture
def company_a_tickets(
    t1_new_unassigned,
    t2_assigned_high,
    t3_in_progress_critical,
    t4_resolved_today,
    t5_closed_two_months_ago,
    t6_outside_trend_window,
) -> list[Ticket]:
    return [
        t1_new_unassigned,
        t2_assigned_high,
        t3_in_progress_critical,
        t4_resolved_today,
        t5_closed_two_months_ago,
        t6_outside_trend_window,
    ]


@pytest.fixture
def company_b_high_priority() -> Priority:
    """Same title as Company A's high_priority - deliberately, to prove
    priority-title grouping is isolated by company_id, not just by the
    title string happening to differ."""
    return Priority(id=201, company_id=COMPANY_B_ID, title="High")


@pytest.fixture
def company_b_hardware_category() -> Category:
    """Same name as Company A's hardware_category - same isolation
    rationale as company_b_high_priority."""
    return Category(id=201, company_id=COMPANY_B_ID, name="Hardware")


@pytest.fixture
def company_b_ticket_same_titles(
    company_b_employee_user, company_b_technician_user, company_b_high_priority, company_b_hardware_category
) -> Ticket:
    t = Ticket(
        id=101,
        company_id=COMPANY_B_ID,
        ticket_number="IT-2026-000001",
        title="B1",
        description="d",
        status=TicketStatus.ASSIGNED,
        priority_id=company_b_high_priority.id,
        category_id=company_b_hardware_category.id,
        created_by_user_id=company_b_employee_user.id,
        assigned_technician_id=company_b_technician_user.id,
        created_at=datetime(2026, 8, 20, 9, 0, 0),
        updated_at=datetime(2026, 8, 20, 9, 0, 0),
    )
    t.priority = company_b_high_priority
    t.category = company_b_hardware_category
    t.created_by = company_b_employee_user
    t.assigned_technician = company_b_technician_user
    return t


def make_analytics_service(tickets: list[Ticket], company_id: int) -> AnalyticsService:
    repo = FakeTicketRepository(tickets, company_id=company_id)
    return AnalyticsService(db=None, company_id=company_id, ticket_repository=repo)


# ---------------------------------------------------------------------------
# Shared ownership scope - the refactor itself
# ---------------------------------------------------------------------------


class TestSharedOwnershipScope:
    def test_company_administrator_scope_is_company_wide(self, active_manager_user):
        scope = TicketService.resolve_ownership_scope(active_manager_user)
        assert scope == TicketOwnershipScope(created_by_user_id=None, assigned_technician_id=None)
        assert scope.is_company_wide is True

    def test_technician_scope_is_assigned_to_self(self, active_technician_user):
        scope = TicketService.resolve_ownership_scope(active_technician_user)
        assert scope == TicketOwnershipScope(
            created_by_user_id=None, assigned_technician_id=active_technician_user.id
        )
        assert scope.is_company_wide is False

    def test_employee_scope_is_created_by_self(self, active_employee_user):
        scope = TicketService.resolve_ownership_scope(active_employee_user)
        assert scope == TicketOwnershipScope(
            created_by_user_id=active_employee_user.id, assigned_technician_id=None
        )
        assert scope.is_company_wide is False

    def test_list_tickets_still_uses_the_same_scope_after_refactor(
        self, active_employee_user, active_technician_user, company_a_tickets
    ):
        """Direct regression check that list_tickets's behavior is
        unchanged after extracting resolve_ownership_scope - the full
        existing suite (test_tickets.py etc.) is the broader proof, this
        is the narrow one co-located with the refactor itself."""
        repo = FakeTicketRepository(company_a_tickets, company_id=COMPANY_A_ID)
        service = TicketService(db=None, company_id=COMPANY_A_ID, ticket_repository=repo)

        employee_tickets = service.list_tickets(active_employee_user)
        assert {t.id for t in employee_tickets} == {1, 2, 4, 6}  # created by employee 1

        technician_tickets = service.list_tickets(active_technician_user)
        assert {t.id for t in technician_tickets} == {2, 3}  # assigned to technician 1


# ---------------------------------------------------------------------------
# Company Administrator - full company-wide analytics
# ---------------------------------------------------------------------------


class TestCompanyAdministratorAnalytics:
    def test_status_breakdown(self, active_manager_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        assert result.by_status == {
            TicketStatus.NEW: 2,
            TicketStatus.ASSIGNED: 1,
            TicketStatus.IN_PROGRESS: 1,
            TicketStatus.RESOLVED: 1,
            TicketStatus.CLOSED: 1,
        }

    def test_priority_breakdown(self, active_manager_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        assert dict(result.by_priority) == {"Low": 2, "High": 1, "Critical": 2, "Medium": 1}

    def test_category_breakdown(self, active_manager_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        assert dict(result.by_category) == {"Hardware": 4, "Software": 2}

    def test_high_priority_open_excludes_terminal_statuses(self, active_manager_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        # T2 (ASSIGNED, High) + T3 (IN_PROGRESS, Critical) count; T5
        # (CLOSED, Critical) is terminal and must not.
        assert result.high_priority_open_count == 2

    def test_unassigned_count(self, active_manager_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        assert result.unassigned_count == 2  # T1, T6

    def test_created_today(self, active_manager_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        assert result.created_today_count == 1  # T1 only

    def test_resolved_today(self, active_manager_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        assert result.resolved_today_count == 1  # T4 only

    def test_average_resolution_minutes(self, active_manager_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        # T4 and T5 both took exactly 1440 minutes (24h) to resolve.
        assert result.avg_resolution_minutes == pytest.approx(1440.0)

    def test_monthly_trend_six_months_including_gaps(self, active_manager_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        labels = [p.month_label for p in result.monthly_trend]
        assert labels == ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]

        by_label = {p.month_label: p for p in result.monthly_trend}
        # Gap months with zero tickets must still appear, with 0 counts.
        assert by_label["2026-03"].created_count == 0
        assert by_label["2026-03"].resolved_count == 0
        assert by_label["2026-04"].created_count == 0
        assert by_label["2026-05"].created_count == 0
        # June: T5 created and resolved.
        assert by_label["2026-06"].created_count == 1
        assert by_label["2026-06"].resolved_count == 1
        # July: T3 created, nothing resolved.
        assert by_label["2026-07"].created_count == 1
        assert by_label["2026-07"].resolved_count == 0
        # August: T1, T2, T4 created; T4 resolved.
        assert by_label["2026-08"].created_count == 3
        assert by_label["2026-08"].resolved_count == 1

    def test_ticket_outside_trend_window_excluded_from_trend_but_not_breakdowns(
        self, active_manager_user, company_a_tickets
    ):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        total_trend_created = sum(p.created_count for p in result.monthly_trend)
        # 5 of the 6 tickets fall in the Mar-Aug window; T6 (January) must
        # not inflate any month's count.
        assert total_trend_created == 5
        # But T6 still counts in the all-time breakdowns.
        assert result.by_status[TicketStatus.NEW] == 2


# ---------------------------------------------------------------------------
# Technician - only assigned tickets affect every aggregate
# ---------------------------------------------------------------------------


class TestTechnicianAnalytics:
    def test_only_assigned_tickets_affect_status_and_priority(
        self, active_technician_user, company_a_tickets
    ):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_technician_user, now=NOW)
        # technician 1 is assigned T2 (ASSIGNED/High) and T3 (IN_PROGRESS/Critical) only.
        assert result.by_status == {TicketStatus.ASSIGNED: 1, TicketStatus.IN_PROGRESS: 1}
        assert dict(result.by_priority) == {"High": 1, "Critical": 1}
        assert result.high_priority_open_count == 2

    def test_other_technicians_tickets_do_not_leak_in(self, active_technician_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_technician_user, now=NOW)
        # T4/T5 (assigned to technician 2) must not appear anywhere.
        assert TicketStatus.RESOLVED not in result.by_status
        assert TicketStatus.CLOSED not in result.by_status
        assert result.avg_resolution_minutes is None  # neither of technician 1's tickets is resolved

    def test_unassigned_count_is_none_for_technician(self, active_technician_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_technician_user, now=NOW)
        assert result.unassigned_count is None

    def test_second_technician_sees_only_their_own_resolution_average(
        self, active_technician_user_2, company_a_tickets
    ):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_technician_user_2, now=NOW)
        assert result.avg_resolution_minutes == pytest.approx(1440.0)  # T4 and T5, both 1440 min
        assert result.resolved_today_count == 1  # T4 only


# ---------------------------------------------------------------------------
# Employee - only own-created tickets affect every aggregate
# ---------------------------------------------------------------------------


class TestEmployeeAnalytics:
    def test_only_own_created_tickets_counted(self, active_employee_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_employee_user, now=NOW)
        # employee 1 created T1, T2, T4, T6.
        assert result.by_status == {
            TicketStatus.NEW: 2,
            TicketStatus.ASSIGNED: 1,
            TicketStatus.RESOLVED: 1,
        }
        assert dict(result.by_category) == {"Hardware": 3, "Software": 1}

    def test_other_employees_tickets_do_not_leak_in(self, active_employee_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_employee_user, now=NOW)
        # T3/T5 (created by employee 2) must not appear.
        assert TicketStatus.IN_PROGRESS not in result.by_status
        assert TicketStatus.CLOSED not in result.by_status

    def test_unassigned_count_is_none_for_employee(self, active_employee_user, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_employee_user, now=NOW)
        assert result.unassigned_count is None

    def test_second_employee_scoped_correctly(self, active_employee_user_2, company_a_tickets):
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_employee_user_2, now=NOW)
        # employee 2 created T3, T5.
        assert result.by_status == {TicketStatus.IN_PROGRESS: 1, TicketStatus.CLOSED: 1}
        assert result.avg_resolution_minutes == pytest.approx(1440.0)  # only T5 resolved


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    def test_company_b_never_affects_company_a_analytics(
        self, active_manager_user, company_a_tickets, company_b_ticket_same_titles
    ):
        all_tickets = company_a_tickets + [company_b_ticket_same_titles]
        service = make_analytics_service(all_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        # Same assertions as the pure-Company-A test above - Company B's
        # ticket must not change a single count.
        assert result.by_status[TicketStatus.NEW] == 2
        assert sum(result.by_status.values()) == 6  # not 7

    def test_identical_priority_titles_stay_isolated_by_company(
        self, active_manager_user, company_a_tickets, company_b_ticket_same_titles
    ):
        all_tickets = company_a_tickets + [company_b_ticket_same_titles]
        service = make_analytics_service(all_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        # Company A has exactly one "High" ticket (T2); Company B's own
        # "High"-titled ticket must not be added to it.
        assert dict(result.by_priority)["High"] == 1

    def test_identical_category_names_stay_isolated_by_company(
        self, active_manager_user, company_a_tickets, company_b_ticket_same_titles
    ):
        all_tickets = company_a_tickets + [company_b_ticket_same_titles]
        service = make_analytics_service(all_tickets, COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        # Company A has 4 "Hardware" tickets; Company B's own
        # "Hardware"-named ticket must not be added to it.
        assert dict(result.by_category)["Hardware"] == 4

    def test_company_b_admin_sees_only_their_own_ticket(
        self, company_b_admin_user, company_a_tickets, company_b_ticket_same_titles
    ):
        all_tickets = company_a_tickets + [company_b_ticket_same_titles]
        service = make_analytics_service(all_tickets, COMPANY_B_ID)
        result = service.get_ticket_analytics(company_b_admin_user, now=NOW)
        assert result.by_status == {TicketStatus.ASSIGNED: 1}
        assert dict(result.by_priority) == {"High": 1}
        assert dict(result.by_category) == {"Hardware": 1}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_tickets_everything_empty_or_zero(self, active_manager_user):
        service = make_analytics_service([], COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        assert result.by_status == {}
        assert result.by_priority == []
        assert result.by_category == []
        assert result.high_priority_open_count == 0
        assert result.unassigned_count == 0
        assert result.created_today_count == 0
        assert result.resolved_today_count == 0
        assert result.avg_resolution_minutes is None
        assert all(p.created_count == 0 and p.resolved_count == 0 for p in result.monthly_trend)
        assert len(result.monthly_trend) == 6

    def test_zero_resolved_tickets_average_is_none(self, active_manager_user, t1_new_unassigned, t2_assigned_high):
        service = make_analytics_service([t1_new_unassigned, t2_assigned_high], COMPANY_A_ID)
        result = service.get_ticket_analytics(active_manager_user, now=NOW)
        assert result.avg_resolution_minutes is None

    def test_nonexistent_scoped_technician_id_returns_empty_not_error(
        self, active_technician_user, company_a_tickets
    ):
        """A technician whose id matches no ticket's assigned_technician_id
        (simulating a scope value that doesn't correspond to any real
        assignment) must get all-zero results, never an error and never
        the company-wide totals."""
        repo = FakeTicketRepository(company_a_tickets, company_id=COMPANY_A_ID)
        by_status = repo.count_grouped_by_status(assigned_technician_id=999999)
        assert by_status == {}
        assert repo.avg_resolution_minutes(assigned_technician_id=999999) is None
        assert repo.count_created_by_boundaries(
            [(datetime(2026, 8, 22, 0, 0, 0), datetime(2026, 8, 23, 0, 0, 0))],
            assigned_technician_id=999999,
        ) == [0]


# ---------------------------------------------------------------------------
# Company-timezone boundary math (independent of AnalyticsService, direct
# unit tests on app.core.time - this is what actually exercises non-UTC
# timezones; every AnalyticsService test above uses Company A, whose
# timezone is "UTC", the trivial case)
# ---------------------------------------------------------------------------


class TestCompanyTimezoneBoundaries:
    def test_utc_company_day_boundary_matches_utc_midnight(self):
        start, end = local_day_boundaries_utc("UTC", now=NOW)
        assert start == datetime(2026, 8, 22, 0, 0, 0)
        assert end == datetime(2026, 8, 23, 0, 0, 0)

    def test_non_utc_company_day_boundary_is_offset(self):
        # 2026-08-22 12:00 UTC = 2026-08-22 08:00 EDT (America/New_York is
        # UTC-4 in August) - the local day is still Aug 22 there, but its
        # UTC boundaries are shifted 4 hours later than UTC's own midnight.
        start, end = local_day_boundaries_utc("America/New_York", now=NOW)
        assert start == datetime(2026, 8, 22, 4, 0, 0)
        assert end == datetime(2026, 8, 23, 4, 0, 0)

    def test_non_utc_company_near_utc_midnight_shifts_the_local_day(self):
        # 2026-08-01 02:00 UTC = 2026-07-31 22:00 EDT - still "July 31"
        # locally, even though the UTC calendar date has already rolled to
        # August 1st. This is exactly the class of bug the UTC
        # normalization prerequisite's day-boundary design exists to avoid.
        reference = datetime(2026, 8, 1, 2, 0, 0, tzinfo=timezone.utc)
        start, end = local_day_boundaries_utc("America/New_York", now=reference)
        assert start == datetime(2026, 7, 31, 4, 0, 0)
        assert end == datetime(2026, 8, 1, 4, 0, 0)

    def test_monthly_boundaries_use_local_calendar_months(self):
        boundaries = local_month_boundaries_utc("America/New_York", 3, now=NOW)
        labels = [label for label, _, _ in boundaries]
        assert labels == ["2026-06", "2026-07", "2026-08"]
        # August's local-calendar start (Aug 1 00:00 EDT) is 04:00 UTC.
        _, start, end = boundaries[-1]
        assert start == datetime(2026, 8, 1, 4, 0, 0)
        assert end == datetime(2026, 9, 1, 4, 0, 0)

    def test_invalid_company_timezone_raises_explicitly(self, active_manager_user, company_a_tickets):
        bad_company = Company(
            id=COMPANY_A_ID,
            name="Company A",
            company_code="COMPANYA",
            theme="light",
            timezone="Not/AZone",
            language="en",
            is_active=True,
        )
        active_manager_user.company = bad_company
        service = make_analytics_service(company_a_tickets, COMPANY_A_ID)
        with pytest.raises(InvalidCompanyTimezoneError):
            service.get_ticket_analytics(active_manager_user, now=NOW)
