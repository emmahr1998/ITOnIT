"""Milestone 8, Phase 8.1: the read-only platform admin backend -
GET /platform/overview, GET /platform/companies, GET /platform/companies/{id}.
System-Administrator-only. Every test class at the bottom also proves the
normal tenant roles are refused and that a company_id appearing in a
platform URL never grants access on its own - see TestPlatformPermissions
and TestPlatformIsolationAndSecurity.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.models.company import Company
from app.models.enums import InventoryStatus, InventoryTrackingType, TicketStatus
from app.models.inventory_category import InventoryCategory
from app.models.inventory_item import InventoryItem
from app.models.ticket import Ticket
from tests.conftest import COMPANY_A_ID, COMPANY_B_ID, SUSPENDED_COMPANY_ID

_PLATFORM_PATHS = ("/platform/overview", "/platform/companies", f"/platform/companies/{COMPANY_A_ID}")


def _reset(repo, rows: list) -> None:
    """Full control over exactly what data a test's requests see - same
    rationale as test_analytics_api.py's _reset_tickets."""
    repo._by_id.clear()
    for row in rows:
        repo._by_id[row.id] = row
    repo._next_id = max((row.id for row in rows), default=0) + 1


def make_company(id_, name, code, *, is_active=True, created_at=None) -> Company:
    now = created_at or datetime.now(timezone.utc)
    return Company(
        id=id_,
        name=name,
        company_code=code,
        theme="light",
        timezone="UTC",
        language="en",
        contact_email=None,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def make_ticket(id_, company_id) -> Ticket:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return Ticket(
        id=id_,
        company_id=company_id,
        ticket_number=f"IT-{id_:06d}",
        title=f"Ticket {id_}",
        description="d",
        status=TicketStatus.NEW,
        priority_id=1,
        category_id=1,
        created_by_user_id=1,
        created_at=now,
        updated_at=now,
    )


def make_item(id_, company_id, category: InventoryCategory) -> InventoryItem:
    item = InventoryItem(
        id=id_,
        company_id=company_id,
        inventory_category_id=category.id,
        name=f"Item {id_}",
        tracking_type=InventoryTrackingType.BULK,
        status=InventoryStatus.AVAILABLE,
        stock_quantity=1,
        reserved_quantity=0,
    )
    item.inventory_category = category
    return item


@pytest.fixture
def three_companies(company_repository) -> list[Company]:
    """Company A active, Company B active, a third inactive - replaces the
    default company_repository baseline (company_a/company_b/
    suspended_company) with explicit, well-separated created_at values, so
    ordering assertions never depend on how close together those fixtures'
    own "now" timestamps happen to land."""
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    companies = [
        make_company(COMPANY_A_ID, "Acme Corp", "ACMECORP1", is_active=True, created_at=base),
        make_company(
            COMPANY_B_ID, "Beta LLC", "BETALLC01", is_active=True, created_at=base + timedelta(days=1)
        ),
        make_company(
            SUSPENDED_COMPANY_ID,
            "Gamma Inc",
            "GAMMAINC1",
            is_active=False,
            created_at=base + timedelta(days=2),
        ),
    ]
    _reset(company_repository, companies)
    return companies


@pytest.fixture
def many_companies(company_repository) -> list[Company]:
    """A richer, deliberately-ordered set for search/filter/sort/pagination
    assertions - not the same three as three_companies, since those tests
    need distinguishable names/codes, not just distinguishable timestamps."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    companies = [
        make_company(1, "Acme Corp", "ACME0001", is_active=True, created_at=base),
        make_company(2, "Acme Robotics", "ACME0002", is_active=True, created_at=base + timedelta(days=1)),
        make_company(3, "Beta LLC", "BETA0001", is_active=False, created_at=base + timedelta(days=2)),
        make_company(4, "Gamma Inc", "GAMMA0001", is_active=True, created_at=base + timedelta(days=3)),
        make_company(5, "Delta Co", "DELTA0001", is_active=False, created_at=base + timedelta(days=4)),
    ]
    _reset(company_repository, companies)
    return companies


class TestPlatformOverview:
    def test_system_administrator_success(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        resp = client.get("/platform/overview", headers=auth_headers(active_system_administrator_user))
        assert resp.status_code == 200

    def test_total_companies_correct(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        resp = client.get("/platform/overview", headers=auth_headers(active_system_administrator_user))
        assert resp.json()["data"]["total_companies"] == 3

    def test_active_and_inactive_counts_correct(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        resp = client.get("/platform/overview", headers=auth_headers(active_system_administrator_user))
        data = resp.json()["data"]
        assert data["active_companies"] == 2
        assert data["inactive_companies"] == 1

    def test_total_users_excludes_company_id_is_null_users(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        # user_repository's default fixture set: 7 Company A users + 3
        # Company B users = 10 tenant users, plus the one platform-level
        # System Administrator (company_id=None) - see conftest.py's
        # user_repository fixture. total_users must be exactly 10, never 11.
        resp = client.get("/platform/overview", headers=auth_headers(active_system_administrator_user))
        assert resp.json()["data"]["total_users"] == 10

    def test_recent_companies_ordering_and_limit(
        self, client: TestClient, auth_headers, active_system_administrator_user, company_repository
    ):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        companies = [
            make_company(1, "Oldest", "OLDEST001", created_at=base),
            make_company(2, "Second", "SECOND001", created_at=base + timedelta(days=1)),
            make_company(3, "Third", "THIRD0001", created_at=base + timedelta(days=2)),
            make_company(4, "Fourth", "FOURTH001", created_at=base + timedelta(days=3)),
            make_company(5, "Fifth", "FIFTH0001", created_at=base + timedelta(days=4)),
            make_company(6, "Newest", "NEWEST001", created_at=base + timedelta(days=5)),
        ]
        _reset(company_repository, companies)
        resp = client.get("/platform/overview", headers=auth_headers(active_system_administrator_user))
        recent = resp.json()["data"]["recent_companies"]
        assert [c["name"] for c in recent] == ["Newest", "Fifth", "Fourth", "Third", "Second"]


class TestPlatformCompanyList:
    def test_search_by_name(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        resp = client.get(
            "/platform/companies?search=acme", headers=auth_headers(active_system_administrator_user)
        )
        names = {c["name"] for c in resp.json()["data"]}
        assert names == {"Acme Corp", "Acme Robotics"}

    def test_search_by_company_code(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        resp = client.get(
            "/platform/companies?search=beta0001",
            headers=auth_headers(active_system_administrator_user),
        )
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Beta LLC"

    def test_active_filter(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        resp = client.get(
            "/platform/companies?is_active=true", headers=auth_headers(active_system_administrator_user)
        )
        data = resp.json()["data"]
        assert len(data) == 3
        assert all(c["is_active"] for c in data)

    def test_inactive_filter(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        resp = client.get(
            "/platform/companies?is_active=false", headers=auth_headers(active_system_administrator_user)
        )
        data = resp.json()["data"]
        assert len(data) == 2
        assert all(not c["is_active"] for c in data)

    def test_pagination(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        resp = client.get(
            "/platform/companies?skip=0&limit=2", headers=auth_headers(active_system_administrator_user)
        )
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["msg"] == "Fetched 2 of 5 companies"

        resp2 = client.get(
            "/platform/companies?skip=4&limit=2", headers=auth_headers(active_system_administrator_user)
        )
        assert len(resp2.json()["data"]) == 1

    def test_sorting_by_name_ascending(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        resp = client.get(
            "/platform/companies?sort_by=name&sort_dir=asc",
            headers=auth_headers(active_system_administrator_user),
        )
        names = [c["name"] for c in resp.json()["data"]]
        assert names == sorted(names)

    def test_unrecognized_sort_field_falls_back_to_created_at(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        """Never accepts an arbitrary column name - an unknown sort_by
        silently falls back to created_at desc, the same convention
        TicketRepository/CompanyRepository's own _SORTABLE_COLUMNS use."""
        resp = client.get(
            "/platform/companies?sort_by=password_hash",
            headers=auth_headers(active_system_administrator_user),
        )
        names = [c["name"] for c in resp.json()["data"]]
        assert names == ["Delta Co", "Gamma Inc", "Beta LLC", "Acme Robotics", "Acme Corp"]

    def test_response_exposes_no_internal_ids(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        resp = client.get("/platform/companies", headers=auth_headers(active_system_administrator_user))
        row = resp.json()["data"][0]
        assert set(row.keys()) == {
            "id",
            "name",
            "company_code",
            "is_active",
            "contact_email",
            "timezone",
            "language",
            "created_at",
        }


class TestPlatformCompanyDetail:
    def test_correct_company(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        resp = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=auth_headers(active_system_administrator_user)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == COMPANY_A_ID
        assert data["name"] == "Acme Corp"
        assert data["company_code"] == "ACMECORP1"

    def test_404_nonexistent_company(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        resp = client.get(
            "/platform/companies/999999", headers=auth_headers(active_system_administrator_user)
        )
        assert resp.status_code == 404

    def test_user_count_correct(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        # Company A's fixture set has exactly 7 users (see conftest.py's
        # user_repository fixture docstring).
        resp = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=auth_headers(active_system_administrator_user)
        )
        assert resp.json()["data"]["user_count"] == 7

    def test_ticket_count_correct(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        three_companies,
        ticket_repository,
    ):
        tickets = [
            make_ticket(1, COMPANY_A_ID),
            make_ticket(2, COMPANY_A_ID),
            make_ticket(3, COMPANY_B_ID),
        ]
        _reset(ticket_repository, tickets)
        resp = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=auth_headers(active_system_administrator_user)
        )
        assert resp.json()["data"]["ticket_count"] == 2

    def test_inventory_item_count_correct(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        three_companies,
        inventory_item_repository,
    ):
        category = InventoryCategory(id=1, company_id=COMPANY_A_ID, name="Cat", is_active=True)
        items = [
            make_item(1, COMPANY_A_ID, category),
            make_item(2, COMPANY_A_ID, category),
            make_item(3, COMPANY_B_ID, category),
        ]
        _reset(inventory_item_repository, items)
        resp = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=auth_headers(active_system_administrator_user)
        )
        assert resp.json()["data"]["inventory_item_count"] == 2


class TestPlatformPermissions:
    @pytest.mark.parametrize("path", _PLATFORM_PATHS)
    def test_unauthenticated_401(self, client: TestClient, path: str):
        assert client.get(path).status_code == 401

    @pytest.mark.parametrize("path", _PLATFORM_PATHS)
    def test_company_administrator_403(
        self, client: TestClient, auth_headers, active_admin_user, path: str
    ):
        resp = client.get(path, headers=auth_headers(active_admin_user))
        assert resp.status_code == 403

    @pytest.mark.parametrize("path", _PLATFORM_PATHS)
    def test_technician_403(
        self, client: TestClient, auth_headers, active_technician_user, path: str
    ):
        resp = client.get(path, headers=auth_headers(active_technician_user))
        assert resp.status_code == 403

    @pytest.mark.parametrize("path", _PLATFORM_PATHS)
    def test_employee_403(
        self, client: TestClient, auth_headers, active_employee_user, path: str
    ):
        resp = client.get(path, headers=auth_headers(active_employee_user))
        assert resp.status_code == 403


class TestPlatformIsolationAndSecurity:
    def test_company_a_detail_ticket_count_excludes_company_b(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        three_companies,
        ticket_repository,
    ):
        tickets = [make_ticket(1, COMPANY_A_ID), make_ticket(2, COMPANY_B_ID), make_ticket(3, COMPANY_B_ID)]
        _reset(ticket_repository, tickets)
        resp_a = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=auth_headers(active_system_administrator_user)
        )
        resp_b = client.get(
            f"/platform/companies/{COMPANY_B_ID}", headers=auth_headers(active_system_administrator_user)
        )
        assert resp_a.json()["data"]["ticket_count"] == 1
        assert resp_b.json()["data"]["ticket_count"] == 2

    def test_company_a_detail_inventory_count_excludes_company_b(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        three_companies,
        inventory_item_repository,
    ):
        category = InventoryCategory(id=1, company_id=COMPANY_A_ID, name="Cat", is_active=True)
        items = [
            make_item(1, COMPANY_A_ID, category),
            make_item(2, COMPANY_B_ID, category),
            make_item(3, COMPANY_B_ID, category),
        ]
        _reset(inventory_item_repository, items)
        resp_a = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=auth_headers(active_system_administrator_user)
        )
        assert resp_a.json()["data"]["inventory_item_count"] == 1

    def test_company_administrators_own_company_id_in_url_grants_no_access(
        self, client: TestClient, auth_headers, active_admin_user
    ):
        """A Company Administrator's own company_id, used as the platform
        URL's {company_id}, still 403s - proving the id in the URL is not
        authorization, only the System-Administrator role check is."""
        resp = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=auth_headers(active_admin_user)
        )
        assert resp.status_code == 403

    def test_company_administrator_cannot_view_another_companys_platform_detail(
        self, client: TestClient, auth_headers, active_admin_user
    ):
        resp = client.get(
            f"/platform/companies/{COMPANY_B_ID}", headers=auth_headers(active_admin_user)
        )
        assert resp.status_code == 403

    def test_system_administrator_gets_no_side_effect_access_to_tenant_endpoints(
        self, client: TestClient, auth_headers, active_system_administrator_user
    ):
        """The company-less System Administrator must not accidentally gain
        access to a normal tenant-scoped endpoint just because the role is
        powerful - it has no company_id for get_current_company_id to
        resolve, so this must 403, never crash and never silently succeed
        with empty/wrong data."""
        resp = client.get(
            "/analytics/tickets", headers=auth_headers(active_system_administrator_user)
        )
        assert resp.status_code == 403
