"""Phase B: GET /analytics/tickets, the HTTP layer over Phase A's
AnalyticsService. Aggregation-logic edge cases (exact GROUP BY correctness,
DATEDIFF precision, etc.) are already exhaustively covered at the
service/repository level in test_analytics.py - this file's job is the HTTP
contract: status codes, role gating, response shape, and that scoping/
tenant-isolation hold end-to-end through the endpoint, not re-deriving
every aggregation case again.
"""
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies.auth import require_roles
from app.models.category import Category
from app.models.enums import TicketStatus
from app.models.priority import Priority
from app.models.ticket import Ticket
from tests.conftest import COMPANY_B_ID, FakeTicketRepository


def _reset_tickets(ticket_repository: FakeTicketRepository, tickets: list[Ticket]) -> None:
    """Full control over exactly what data this test's requests see -
    the fixture ticket_repository the shared `client` fixture wires up
    starts pre-loaded with fixtures meant for other test files; analytics
    tests need a precisely known set instead."""
    ticket_repository._by_id.clear()
    for t in tickets:
        ticket_repository._by_id[t.id] = t
    ticket_repository._next_id = max((t.id for t in tickets), default=0) + 1


def make_ticket(
    id_, status, priority, category, created_by, assigned_to, created_at, resolved_at=None,
    company_id=1,
) -> Ticket:
    t = Ticket(
        id=id_, company_id=company_id, ticket_number=f"IT-{id_:06d}", title=f"T{id_}",
        description="d", status=status, priority_id=priority.id, category_id=category.id,
        created_by_user_id=created_by.id, assigned_technician_id=assigned_to.id if assigned_to else None,
        created_at=created_at, updated_at=created_at, resolved_at=resolved_at,
    )
    t.priority = priority
    t.category = category
    t.created_by = created_by
    t.assigned_technician = assigned_to
    return t


@pytest.fixture
def analytics_tickets(
    active_employee_user, active_employee_user_2, active_technician_user, active_technician_user_2,
    low_priority, high_priority, critical_priority, hardware_category, software_category,
) -> list[Ticket]:
    today = datetime.now(timezone.utc).replace(tzinfo=None).replace(hour=9, minute=0, second=0, microsecond=0)
    return [
        make_ticket(1, TicketStatus.NEW, low_priority, hardware_category, active_employee_user, None, today),
        make_ticket(
            2, TicketStatus.ASSIGNED, high_priority, software_category,
            active_employee_user, active_technician_user, today,
        ),
        make_ticket(
            3, TicketStatus.IN_PROGRESS, critical_priority, hardware_category,
            active_employee_user_2, active_technician_user, today,
        ),
        make_ticket(
            4, TicketStatus.RESOLVED, high_priority, hardware_category,
            active_employee_user_2, active_technician_user_2, today, resolved_at=today,
        ),
    ]


class TestRoleResponses:
    def test_company_administrator_sees_company_wide_analytics(
        self, client: TestClient, auth_headers, active_manager_user, ticket_repository, analytics_tickets
    ):
        _reset_tickets(ticket_repository, analytics_tickets)
        resp = client.get("/analytics/tickets", headers=auth_headers(active_manager_user))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert sum(item["count"] for item in data["by_status"]) == 4
        assert data["unassigned_count"] == 1  # ticket 1
        assert data["high_priority_open_count"] == 2  # ticket 2 (ASSIGNED/High), ticket 3 (IN_PROGRESS/Critical)

    def test_technician_sees_only_assigned_tickets(
        self, client: TestClient, auth_headers, active_technician_user, ticket_repository, analytics_tickets
    ):
        _reset_tickets(ticket_repository, analytics_tickets)
        resp = client.get("/analytics/tickets", headers=auth_headers(active_technician_user))
        assert resp.status_code == 200
        data = resp.json()["data"]
        # technician (id=4) is assigned tickets 2 and 3 only.
        assert sum(item["count"] for item in data["by_status"]) == 2
        assert data["unassigned_count"] is None

    def test_employee_sees_only_own_created_tickets(
        self, client: TestClient, auth_headers, active_employee_user, ticket_repository, analytics_tickets
    ):
        _reset_tickets(ticket_repository, analytics_tickets)
        resp = client.get("/analytics/tickets", headers=auth_headers(active_employee_user))
        assert resp.status_code == 200
        data = resp.json()["data"]
        # employee (id=3) created tickets 1 and 2 only.
        assert sum(item["count"] for item in data["by_status"]) == 2
        assert data["unassigned_count"] is None


class TestResponseShape:
    def test_response_contains_all_required_fields(
        self, client: TestClient, auth_headers, active_manager_user, ticket_repository, analytics_tickets
    ):
        _reset_tickets(ticket_repository, analytics_tickets)
        resp = client.get("/analytics/tickets", headers=auth_headers(active_manager_user))
        data = resp.json()["data"]
        for field in (
            "open_count", "in_progress_count", "waiting_for_employee_count",
            "high_priority_open_count", "unassigned_count", "created_today",
            "resolved_today", "avg_resolution_minutes", "by_status", "by_priority",
            "by_category", "monthly_trend",
        ):
            assert field in data, f"missing field: {field}"

        assert data["in_progress_count"] == 1  # ticket 3
        for item in data["by_status"]:
            assert set(item.keys()) == {"status", "count"}
        for item in data["by_priority"]:
            assert set(item.keys()) == {"priority", "count"}
        for item in data["by_category"]:
            assert set(item.keys()) == {"category", "count"}
        for item in data["monthly_trend"]:
            assert set(item.keys()) == {"month", "created", "resolved"}


class TestEdgeCases:
    def test_no_tickets(
        self, client: TestClient, auth_headers, active_manager_user, ticket_repository
    ):
        _reset_tickets(ticket_repository, [])
        resp = client.get("/analytics/tickets", headers=auth_headers(active_manager_user))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["by_status"] == []
        assert data["by_priority"] == []
        assert data["by_category"] == []
        assert data["open_count"] == 0
        assert data["unassigned_count"] == 0
        assert data["avg_resolution_minutes"] is None
        assert len(data["monthly_trend"]) == 6

    def test_no_resolved_tickets_average_is_null(
        self, client: TestClient, auth_headers, active_manager_user, ticket_repository, analytics_tickets
    ):
        unresolved_only = [t for t in analytics_tickets if t.resolved_at is None]
        _reset_tickets(ticket_repository, unresolved_only)
        resp = client.get("/analytics/tickets", headers=auth_headers(active_manager_user))
        assert resp.json()["data"]["avg_resolution_minutes"] is None

    def test_monthly_trend_has_six_months_with_zero_count_months(
        self, client: TestClient, auth_headers, active_manager_user, ticket_repository, analytics_tickets
    ):
        _reset_tickets(ticket_repository, analytics_tickets)
        resp = client.get("/analytics/tickets", headers=auth_headers(active_manager_user))
        trend = resp.json()["data"]["monthly_trend"]
        assert len(trend) == 6
        # All 4 fixture tickets are dated "today" (this month) - every
        # other month in the window must still appear, with zero counts.
        zero_months = [p for p in trend if p["created"] == 0 and p["resolved"] == 0]
        assert len(zero_months) == 5

    def test_invalid_company_timezone_returns_clear_error_not_internals(
        self, client: TestClient, auth_headers, active_manager_user, company_a, ticket_repository
    ):
        _reset_tickets(ticket_repository, [])
        original_timezone = company_a.timezone
        company_a.timezone = "Not/ARealZone"
        try:
            resp = client.get("/analytics/tickets", headers=auth_headers(active_manager_user))
            assert resp.status_code == 500
            detail = resp.json()["detail"]
            # A clear, generic message - never the raw exception, a stack
            # trace, or any SQL/database detail.
            assert "Not/ARealZone" not in detail
            assert "traceback" not in detail.lower()
            assert "sql" not in detail.lower()
        finally:
            company_a.timezone = original_timezone


class TestAuthAndPermissions:
    def test_unauthenticated_request_is_rejected(self, client: TestClient):
        resp = client.get("/analytics/tickets")
        assert resp.status_code == 401

    def test_role_not_in_allowed_set_is_rejected(self):
        """No real user in this system can reach GET /analytics/tickets
        with an unsupported role through the normal login flow - Employee,
        Technician, and Company Administrator (the only roles a
        company-scoped user can ever have) are all allowed, and a
        company-scoped System Administrator user cannot exist by this
        codebase's own design (see get_current_company_id's docstring).
        This tests the require_roles guard mechanism itself directly,
        rather than fabricating an unrepresentative fixture."""

        class _FakeRole:
            name = "Some Other Role"

        class _FakeUser:
            role = _FakeRole()

        guard = require_roles("Employee", "Technician", "Company Administrator")
        with pytest.raises(HTTPException) as exc_info:
            guard(current_user=_FakeUser())
        assert exc_info.value.status_code == 403


class TestTenantIsolation:
    def test_company_b_ticket_never_affects_company_a_response(
        self, client: TestClient, auth_headers, active_manager_user, ticket_repository,
        analytics_tickets, company_b_employee_user, company_b_technician_user,
    ):
        # Company B ticket deliberately uses the SAME priority/category
        # titles as Company A's data ("High", "Hardware") to prove
        # isolation is by company_id, not by these names happening to differ.
        b_high = Priority(id=901, company_id=COMPANY_B_ID, title="High")
        b_hardware = Category(id=901, company_id=COMPANY_B_ID, name="Hardware")
        today = datetime.now(timezone.utc).replace(tzinfo=None)
        b_ticket = make_ticket(
            101, TicketStatus.ASSIGNED, b_high, b_hardware,
            company_b_employee_user, company_b_technician_user, today, company_id=COMPANY_B_ID,
        )
        _reset_tickets(ticket_repository, analytics_tickets + [b_ticket])

        resp = client.get("/analytics/tickets", headers=auth_headers(active_manager_user))
        data = resp.json()["data"]
        assert sum(item["count"] for item in data["by_status"]) == 4  # not 5
        by_priority = {item["priority"]: item["count"] for item in data["by_priority"]}
        # Company A's own "High" tickets are 2 and 4 (=2) - Company B's own
        # "High"-titled ticket must not make this 3.
        assert by_priority["High"] == 2
        by_category = {item["category"]: item["count"] for item in data["by_category"]}
        # Company A's own "Hardware" tickets are 1, 3, and 4 (=3) - Company
        # B's own "Hardware"-named ticket must not make this 4.
        assert by_category["Hardware"] == 3

    def test_request_parameters_cannot_influence_company_scope(
        self, client: TestClient, auth_headers, active_manager_user, ticket_repository, analytics_tickets
    ):
        """company_id must come only from the authenticated user - proven
        by showing that query-string/body attempts to smuggle a different
        one change nothing about the response (the endpoint takes no such
        parameter at all, so these are simply ignored, not honored)."""
        _reset_tickets(ticket_repository, analytics_tickets)
        baseline = client.get("/analytics/tickets", headers=auth_headers(active_manager_user)).json()["data"]

        tampered = client.get(
            "/analytics/tickets",
            params={"company_id": 999999},
            headers=auth_headers(active_manager_user),
        ).json()["data"]
        assert tampered == baseline

        tampered_body = client.request(
            "GET",
            "/analytics/tickets",
            json={"company_id": 999999},
            headers=auth_headers(active_manager_user),
        ).json()["data"]
        assert tampered_body == baseline
