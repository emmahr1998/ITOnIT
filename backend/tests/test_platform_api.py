"""Milestone 8: the platform admin backend.

Phase 8.1 - the read-only surface: GET /platform/overview,
GET /platform/companies, GET /platform/companies/{id}.

Phase 8.2 - the one mutation surface: PATCH /platform/companies/{id}/
activate and /deactivate, and the end-to-end proof that deactivating a
company through this endpoint actually engages the *existing*,
already-tested suspension checks in AuthService/get_current_active_user
(see TestPlatformDeactivationSemantics) rather than reimplementing them.

Phase 8.3 - POST /platform/login and the System Administrator bootstrap
(see TestPlatformLogin) - the critical property under test throughout that
class is that the lookup is restricted to company_id IS NULL, so a real
tenant user's correct credentials can never authenticate here.

System-Administrator-only throughout. Every permission test class also
proves the normal tenant roles are refused and that a company_id appearing
in a platform URL never grants access on its own.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.company import Company
from app.models.enums import InventoryStatus, InventoryTrackingType, TicketStatus
from app.models.inventory_category import InventoryCategory
from app.models.inventory_item import InventoryItem
from app.models.ticket import Ticket
from app.models.user import User
from app.scripts.seed_initial_data import _seed_platform_administrator
from tests.conftest import (
    ADMIN_PASSWORD,
    COMPANY_A_ID,
    COMPANY_B_ADMIN_PASSWORD,
    COMPANY_B_ID,
    EMPLOYEE_PASSWORD,
    SUSPENDED_COMPANY_ID,
)

_PLATFORM_PATHS = ("/platform/overview", "/platform/companies", f"/platform/companies/{COMPANY_A_ID}")
_ACTIVATE_PATH = f"/platform/companies/{COMPANY_A_ID}/activate"
_DEACTIVATE_PATH = f"/platform/companies/{COMPANY_A_ID}/deactivate"


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
        assert body["total"] == 5
        assert body["msg"] == "Fetched 2 of 5 companies"

        resp2 = client.get(
            "/platform/companies?skip=4&limit=2", headers=auth_headers(active_system_administrator_user)
        )
        assert len(resp2.json()["data"]) == 1

    def test_total_with_no_filters(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        """5 companies exist in total (many_companies) - total must be the
        full unfiltered count, not the page size."""
        resp = client.get("/platform/companies", headers=auth_headers(active_system_administrator_user))
        assert resp.json()["total"] == 5

    def test_total_with_search(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        """many_companies has exactly 2 "acme" matches (Acme Corp, Acme
        Robotics) - total must reflect the search filter, not the
        unfiltered count of 5."""
        resp = client.get(
            "/platform/companies?search=acme", headers=auth_headers(active_system_administrator_user)
        )
        body = resp.json()
        assert body["total"] == 2
        assert len(body["data"]) == 2

    def test_total_with_is_active_true(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        """many_companies has exactly 3 active companies."""
        resp = client.get(
            "/platform/companies?is_active=true", headers=auth_headers(active_system_administrator_user)
        )
        assert resp.json()["total"] == 3

    def test_total_with_is_active_false(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        """many_companies has exactly 2 inactive companies."""
        resp = client.get(
            "/platform/companies?is_active=false", headers=auth_headers(active_system_administrator_user)
        )
        assert resp.json()["total"] == 2

    def test_total_is_filtered_count_not_page_size_when_limit_smaller(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        """With is_active=true (3 matches) and limit=2, the page has 2 rows
        but total must still report 3 - the full filtered count computed
        before skip/limit, never len(data)."""
        resp = client.get(
            "/platform/companies?is_active=true&limit=2",
            headers=auth_headers(active_system_administrator_user),
        )
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["total"] == 3

    def test_skip_does_not_change_total(
        self, client: TestClient, auth_headers, active_system_administrator_user, many_companies
    ):
        """Paging deeper (skip=4) still reports the same total of 5 - total
        is computed independently of skip/limit, not derived from the page
        actually returned."""
        resp = client.get(
            "/platform/companies?skip=4&limit=2", headers=auth_headers(active_system_administrator_user)
        )
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["total"] == 5

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


# ===========================================================================
# Phase 8.2 - PATCH /platform/companies/{id}/activate and /deactivate
# ===========================================================================

_ACTIVATE_DEACTIVATE_PATHS = (_ACTIVATE_PATH, _DEACTIVATE_PATH)


class TestPlatformActivateDeactivate:
    def test_deactivate_active_company_succeeds(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        resp = client.patch(_DEACTIVATE_PATH, headers=auth_headers(active_system_administrator_user))
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is False

    def test_activate_inactive_company_succeeds(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        path = f"/platform/companies/{SUSPENDED_COMPANY_ID}/activate"
        resp = client.patch(path, headers=auth_headers(active_system_administrator_user))
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is True

    def test_deactivate_is_idempotent(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        headers = auth_headers(active_system_administrator_user)
        first = client.patch(_DEACTIVATE_PATH, headers=headers)
        second = client.patch(_DEACTIVATE_PATH, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["data"]["is_active"] is False

    def test_activate_is_idempotent(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        headers = auth_headers(active_system_administrator_user)
        first = client.patch(_ACTIVATE_PATH, headers=headers)
        second = client.patch(_ACTIVATE_PATH, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["data"]["is_active"] is True

    def test_deactivate_nonexistent_company_404(
        self, client: TestClient, auth_headers, active_system_administrator_user
    ):
        resp = client.patch(
            "/platform/companies/999999/deactivate",
            headers=auth_headers(active_system_administrator_user),
        )
        assert resp.status_code == 404

    def test_activate_nonexistent_company_404(
        self, client: TestClient, auth_headers, active_system_administrator_user
    ):
        resp = client.patch(
            "/platform/companies/999999/activate",
            headers=auth_headers(active_system_administrator_user),
        )
        assert resp.status_code == 404

    def test_deactivate_only_changes_is_active_no_other_field(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        before = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=auth_headers(active_system_administrator_user)
        ).json()["data"]
        resp = client.patch(_DEACTIVATE_PATH, headers=auth_headers(active_system_administrator_user))
        after = resp.json()["data"]
        assert after["is_active"] is False
        for field in ("id", "name", "company_code", "contact_email", "timezone", "language"):
            assert after[field] == before[field]


class TestPlatformActivateDeactivatePermissions:
    @pytest.mark.parametrize("path", _ACTIVATE_DEACTIVATE_PATHS)
    def test_unauthenticated_401(self, client: TestClient, path: str):
        assert client.patch(path).status_code == 401

    @pytest.mark.parametrize("path", _ACTIVATE_DEACTIVATE_PATHS)
    def test_company_administrator_403(
        self, client: TestClient, auth_headers, active_admin_user, path: str
    ):
        resp = client.patch(path, headers=auth_headers(active_admin_user))
        assert resp.status_code == 403

    @pytest.mark.parametrize("path", _ACTIVATE_DEACTIVATE_PATHS)
    def test_technician_403(
        self, client: TestClient, auth_headers, active_technician_user, path: str
    ):
        resp = client.patch(path, headers=auth_headers(active_technician_user))
        assert resp.status_code == 403

    @pytest.mark.parametrize("path", _ACTIVATE_DEACTIVATE_PATHS)
    def test_employee_403(
        self, client: TestClient, auth_headers, active_employee_user, path: str
    ):
        resp = client.patch(path, headers=auth_headers(active_employee_user))
        assert resp.status_code == 403


class TestPlatformDeactivationSemantics:
    """The critical Phase 8.2 behavior: deactivating through the platform
    endpoint must engage the *existing*, already-tested suspension checks
    in AuthService/get_current_active_user (see test_auth.py's own
    suspended-company tests) - this class proves the platform endpoint
    actually triggers them end-to-end, not that the checks themselves work
    (already proven). Deliberately uses the plain company_a/active_admin_user
    fixtures (not three_companies), since these tests need real, known
    login credentials and company codes.
    """

    def test_deactivation_blocks_resolve_company(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        company_a: Company,
    ):
        deactivate_path = f"/platform/companies/{COMPANY_A_ID}/deactivate"
        resp = client.patch(deactivate_path, headers=auth_headers(active_system_administrator_user))
        assert resp.status_code == 200

        resolved = client.post(
            "/auth/resolve-company", json={"company_code": company_a.company_code}
        )
        assert resolved.status_code == 403
        assert resolved.json()["detail"] == "This company's account has been suspended"

    def test_deactivation_blocks_new_login(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        active_admin_user: User,
        company_a: Company,
    ):
        deactivate_path = f"/platform/companies/{COMPANY_A_ID}/deactivate"
        resp = client.patch(deactivate_path, headers=auth_headers(active_system_administrator_user))
        assert resp.status_code == 200

        login_resp = client.post(
            "/auth/login",
            json={
                "company_code": company_a.company_code,
                "username": active_admin_user.username,
                "password": ADMIN_PASSWORD,
            },
        )
        assert login_resp.status_code == 403
        assert login_resp.json()["detail"] == "This company's account has been suspended"

    def test_deactivation_revokes_an_already_issued_valid_token(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        active_admin_user: User,
    ):
        """Obtains a real tenant access token BEFORE deactivation, confirms
        it works, deactivates Company A through the platform endpoint, then
        proves the SAME still-unexpired token now fails - the platform
        endpoint never touches tokens directly, this is entirely
        get_current_active_user's existing per-request check reacting to
        the is_active flip."""
        token = create_access_token(subject=active_admin_user.id)
        still_active = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert still_active.status_code == 200

        deactivate_path = f"/platform/companies/{COMPANY_A_ID}/deactivate"
        resp = client.patch(deactivate_path, headers=auth_headers(active_system_administrator_user))
        assert resp.status_code == 200

        now_suspended = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert now_suspended.status_code == 403
        assert now_suspended.json()["detail"] == "This company's account has been suspended"

    def test_reactivation_restores_resolve_company_and_login(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        active_admin_user: User,
        company_a: Company,
    ):
        headers = auth_headers(active_system_administrator_user)
        deactivate_path = f"/platform/companies/{COMPANY_A_ID}/deactivate"
        activate_path = f"/platform/companies/{COMPANY_A_ID}/activate"

        client.patch(deactivate_path, headers=headers)
        blocked = client.post(
            "/auth/resolve-company", json={"company_code": company_a.company_code}
        )
        assert blocked.status_code == 403

        reactivate_resp = client.patch(activate_path, headers=headers)
        assert reactivate_resp.status_code == 200

        resolved = client.post(
            "/auth/resolve-company", json={"company_code": company_a.company_code}
        )
        assert resolved.status_code == 200

        login_resp = client.post(
            "/auth/login",
            json={
                "company_code": company_a.company_code,
                "username": active_admin_user.username,
                "password": ADMIN_PASSWORD,
            },
        )
        assert login_resp.status_code == 200


class TestPlatformDeactivationDataPreservation:
    def test_deactivate_and_reactivate_preserve_all_counts(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        headers = auth_headers(active_system_administrator_user)
        detail_url = f"/platform/companies/{COMPANY_A_ID}"

        before = client.get(detail_url, headers=headers).json()["data"]
        client.patch(_DEACTIVATE_PATH, headers=headers)
        during = client.get(detail_url, headers=headers).json()["data"]
        client.patch(_ACTIVATE_PATH, headers=headers)
        after = client.get(detail_url, headers=headers).json()["data"]

        for snapshot in (during, after):
            assert snapshot["user_count"] == before["user_count"]
            assert snapshot["ticket_count"] == before["ticket_count"]
            assert snapshot["inventory_item_count"] == before["inventory_item_count"]
            assert snapshot["name"] == before["name"]
            assert snapshot["company_code"] == before["company_code"]
            assert snapshot["timezone"] == before["timezone"]
            assert snapshot["language"] == before["language"]

    def test_deactivate_does_not_remove_users_from_the_company(
        self, client: TestClient, auth_headers, active_system_administrator_user, three_companies
    ):
        """A lightweight direct check on the underlying fake store (mirrors
        a real-DB row-count check) - proves no cascade delete happens."""
        headers = auth_headers(active_system_administrator_user)
        before = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=headers
        ).json()["data"]["user_count"]
        client.patch(_DEACTIVATE_PATH, headers=headers)
        after = client.get(
            f"/platform/companies/{COMPANY_A_ID}", headers=headers
        ).json()["data"]["user_count"]
        assert after == before

    def test_deactivate_and_reactivate_touch_no_other_tenant_table(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        three_companies,
        user_repository,
        ticket_repository,
        comment_repository,
        attachment_repository,
        history_repository,
        inventory_item_repository,
        inventory_category_repository,
        category_repository,
        priority_repository,
        location_repository,
    ):
        """The active-state toggle must not delete or alter a single row in
        any tenant table for Company A - a direct row-count snapshot of
        every repository the client fixture wires up (mirrors what a real
        before/after SELECT COUNT(*) per table would show), taken before
        deactivation and compared after deactivate+reactivate."""

        def _company_a_counts() -> dict[str, int]:
            by_id_repos = {
                "users": user_repository,
                "tickets": ticket_repository,
                "comments": comment_repository,
                "attachments": attachment_repository,
                "inventory_items": inventory_item_repository,
                "inventory_categories": inventory_category_repository,
                "categories": category_repository,
                "priorities": priority_repository,
                "locations": location_repository,
            }
            counts = {
                name: sum(1 for row in repo._by_id.values() if row.company_id == COMPANY_A_ID)
                for name, repo in by_id_repos.items()
            }
            # FakeHistoryRepository stores rows in a plain list, not a dict
            # keyed by id (see conftest.py's own class) - same idea, different
            # underlying container.
            counts["ticket_history"] = sum(
                1 for row in history_repository._entries if row.company_id == COMPANY_A_ID
            )
            return counts

        before = _company_a_counts()

        headers = auth_headers(active_system_administrator_user)
        client.patch(_DEACTIVATE_PATH, headers=headers)
        during = _company_a_counts()
        client.patch(_ACTIVATE_PATH, headers=headers)
        after = _company_a_counts()

        assert during == before
        assert after == before


class TestPlatformDeactivationCompanyBIsolation:
    def test_deactivating_company_a_does_not_affect_company_b_login(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        company_a: Company,
        company_b_admin_user: User,
        company_b: Company,
    ):
        deactivate_path = f"/platform/companies/{COMPANY_A_ID}/deactivate"
        resp = client.patch(deactivate_path, headers=auth_headers(active_system_administrator_user))
        assert resp.status_code == 200
        assert company_a.is_active is False
        assert company_b.is_active is True

        login_resp = client.post(
            "/auth/login",
            json={
                "company_code": company_b.company_code,
                "username": company_b_admin_user.username,
                "password": COMPANY_B_ADMIN_PASSWORD,
            },
        )
        assert login_resp.status_code == 200

    def test_deactivating_company_a_does_not_affect_company_bs_platform_detail(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        three_companies,
    ):
        headers = auth_headers(active_system_administrator_user)
        before_b = client.get(f"/platform/companies/{COMPANY_B_ID}", headers=headers).json()["data"]
        client.patch(_DEACTIVATE_PATH, headers=headers)
        after_b = client.get(f"/platform/companies/{COMPANY_B_ID}", headers=headers).json()["data"]
        assert after_b["is_active"] is True
        assert after_b == before_b


# ===========================================================================
# Phase 8.3 - POST /platform/login and the System Administrator bootstrap
# ===========================================================================

_PLATFORM_ADMIN_PASSWORD = "PlatformAdminPass1!"  # matches active_system_administrator_user


class TestPlatformLogin:
    def test_valid_platform_administrator_login_succeeds(
        self, client: TestClient, active_system_administrator_user: User
    ):
        resp = client.post(
            "/platform/login",
            json={"username": active_system_administrator_user.username, "password": _PLATFORM_ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access" in body and "refresh" in body
        assert body["token_type"] == "bearer"

    def test_returned_access_token_works_with_auth_me(
        self, client: TestClient, active_system_administrator_user: User
    ):
        login_resp = client.post(
            "/platform/login",
            json={"username": active_system_administrator_user.username, "password": _PLATFORM_ADMIN_PASSWORD},
        )
        token = login_resp.json()["access"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["role"] == "System Administrator"

    def test_login_by_email_also_succeeds(
        self, client: TestClient, active_system_administrator_user: User
    ):
        resp = client.post(
            "/platform/login",
            json={"username": active_system_administrator_user.email, "password": _PLATFORM_ADMIN_PASSWORD},
        )
        assert resp.status_code == 200

    def test_wrong_password_generic_401(
        self, client: TestClient, active_system_administrator_user: User
    ):
        resp = client.post(
            "/platform/login",
            json={"username": active_system_administrator_user.username, "password": "WrongPassword1!"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

    def test_unknown_identifier_generic_401(self, client: TestClient):
        resp = client.post(
            "/platform/login", json={"username": "nobody_at_all", "password": "WhateverPass1!"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

    def test_inactive_platform_administrator_generic_401(
        self, client: TestClient, active_system_administrator_user: User
    ):
        active_system_administrator_user.is_active = False
        resp = client.post(
            "/platform/login",
            json={"username": active_system_administrator_user.username, "password": _PLATFORM_ADMIN_PASSWORD},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"
        active_system_administrator_user.is_active = True

    def test_tenant_username_with_correct_tenant_password_rejected(
        self, client: TestClient, active_admin_user: User
    ):
        """The critical isolation test: a real tenant Company Administrator's
        own username and correct password must NOT authenticate through
        the platform login - the lookup is restricted to company_id IS
        NULL, so this tenant user is structurally invisible to it."""
        resp = client.post(
            "/platform/login",
            json={"username": active_admin_user.username, "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

    def test_tenant_email_with_correct_tenant_password_rejected(
        self, client: TestClient, active_employee_user: User
    ):
        resp = client.post(
            "/platform/login",
            json={"username": active_employee_user.email, "password": EMPLOYEE_PASSWORD},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

    def test_platform_administrator_cannot_authenticate_through_tenant_login(
        self, client: TestClient, active_system_administrator_user: User, company_a: Company
    ):
        """The reverse isolation direction: the platform account has no
        company, so it can't log in through the tenant flow no matter what
        company_code is supplied."""
        resp = client.post(
            "/auth/login",
            json={
                "company_code": company_a.company_code,
                "username": active_system_administrator_user.username,
                "password": _PLATFORM_ADMIN_PASSWORD,
            },
        )
        assert resp.status_code == 401

    def test_platform_login_does_not_require_or_accept_company_code(
        self, client: TestClient, active_system_administrator_user: User
    ):
        """A company_code sent anyway is simply ignored (extra fields are
        not part of PlatformLoginRequest's schema) - the request still
        succeeds on username/password alone."""
        resp = client.post(
            "/platform/login",
            json={
                "company_code": "SHOULD-BE-IGNORED",
                "username": active_system_administrator_user.username,
                "password": _PLATFORM_ADMIN_PASSWORD,
            },
        )
        assert resp.status_code == 200

    def test_platform_login_missing_password_is_a_validation_error(self, client: TestClient):
        resp = client.post("/platform/login", json={"username": "platform_admin"})
        assert resp.status_code == 422

    def test_existing_phase_8_1_permissions_unaffected(
        self, client: TestClient, auth_headers, active_admin_user: User
    ):
        """Adding the public /login route must not loosen the existing
        System-Administrator-only gate on the read/write platform routes."""
        resp = client.get("/platform/overview", headers=auth_headers(active_admin_user))
        assert resp.status_code == 403

    def test_existing_phase_8_2_permissions_unaffected(
        self, client: TestClient, auth_headers, active_admin_user: User
    ):
        resp = client.patch(_DEACTIVATE_PATH, headers=auth_headers(active_admin_user))
        assert resp.status_code == 403


class TestPlatformAdministratorSeed:
    """Unit tests for the bootstrap function itself, isolated from the HTTP
    layer - mirrors how this codebase would test any other seed-script
    function, using the same fake repositories as everywhere else."""

    def test_seed_skipped_when_configuration_absent(
        self, monkeypatch: pytest.MonkeyPatch, user_repository, role_repository
    ):

        monkeypatch.setattr("app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_EMAIL", None)
        monkeypatch.setattr("app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_PASSWORD", None)
        before = len(user_repository._by_id)
        _seed_platform_administrator(user_repository, role_repository)
        assert len(user_repository._by_id) == before

    def test_seed_creates_expected_company_id_null_system_administrator(
        self, monkeypatch: pytest.MonkeyPatch, user_repository, role_repository
    ):

        monkeypatch.setattr(
            "app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_EMAIL",
            "new_platform_admin@itonit.test",
        )
        monkeypatch.setattr(
            "app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_PASSWORD", "SeedTestPass1!"
        )
        monkeypatch.setattr(
            "app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_FIRST_NAME", None
        )
        monkeypatch.setattr(
            "app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_LAST_NAME", None
        )
        _seed_platform_administrator(user_repository, role_repository)
        created = user_repository.get_platform_administrator("new_platform_admin@itonit.test")
        assert created is not None
        assert created.company_id is None
        # role_id, not created.role.name: the fake's create() doesn't
        # populate the .role relationship the way a real, session-attached
        # ORM object would lazy-load it - this is a fake-only limitation,
        # not something the real seed script needs to work around.
        expected_role = role_repository.get_by_name("System Administrator")
        assert created.role_id == expected_role.id

    def test_seed_run_twice_does_not_create_a_duplicate(
        self, monkeypatch: pytest.MonkeyPatch, user_repository, role_repository
    ):

        monkeypatch.setattr(
            "app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_EMAIL",
            "twice_platform_admin@itonit.test",
        )
        monkeypatch.setattr(
            "app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_PASSWORD", "SeedTestPass1!"
        )
        _seed_platform_administrator(user_repository, role_repository)
        after_first = len(user_repository._by_id)
        _seed_platform_administrator(user_repository, role_repository)
        after_second = len(user_repository._by_id)
        assert after_second == after_first

    def test_seed_does_not_mutate_an_existing_platform_account(
        self,
        monkeypatch: pytest.MonkeyPatch,
        user_repository,
        role_repository,
        active_system_administrator_user: User,
    ):
        """Re-running the seed against an already-provisioned platform
        account must leave it untouched - no field is rewritten, no new
        row created, matching _seed_admin_user's own idempotency
        contract."""
        monkeypatch.setattr(
            "app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_EMAIL",
            active_system_administrator_user.email,
        )
        monkeypatch.setattr(
            "app.scripts.seed_initial_data.settings.PLATFORM_ADMIN_PASSWORD", "SomeOtherPass1!"
        )
        original_hash = active_system_administrator_user.password_hash
        before = len(user_repository._by_id)
        _seed_platform_administrator(user_repository, role_repository)
        assert len(user_repository._by_id) == before
        assert active_system_administrator_user.password_hash == original_hash


# ===========================================================================
# Phase 8.4 - POST /platform/companies (company provisioning)
# ===========================================================================


def _platform_company_payload(**overrides: object) -> dict:
    payload = {
        "company_name": "Provisioned Co",
        "company_code": "PROV0001",
        "first_name": "Pat",
        "last_name": "Admin",
        "username": "patadmin",
        "email": "pat@provisioned.test",
        "password": "SuperSecret1!",
    }
    payload.update(overrides)
    return payload


class TestPlatformCreateCompany:
    def test_system_administrator_creates_company_201(
        self, client: TestClient, auth_headers, active_system_administrator_user
    ):
        resp = client.post(
            "/platform/companies",
            json=_platform_company_payload(),
            headers=auth_headers(active_system_administrator_user),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Provisioned Co"
        assert data["company_code"] == "PROV0001"
        assert data["user_count"] == 1
        assert data["ticket_count"] == 0
        assert data["inventory_item_count"] == 0

    def test_response_contains_no_tokens(
        self, client: TestClient, auth_headers, active_system_administrator_user
    ):
        resp = client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROV0002"),
            headers=auth_headers(active_system_administrator_user),
        )
        body = resp.json()
        assert "access" not in body
        assert "refresh" not in body
        assert "access" not in body["data"]
        assert "refresh" not in body["data"]

    def test_duplicate_company_code_matches_self_registration_409(
        self, client: TestClient, auth_headers, active_system_administrator_user
    ):
        headers = auth_headers(active_system_administrator_user)
        client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROVDUP1"),
            headers=headers,
        )
        resp = client.post(
            "/platform/companies",
            json=_platform_company_payload(
                company_code="PROVDUP1",
                username="anotheradmin",
                email="another@provisioned.test",
            ),
            headers=headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "A company with this company code already exists"

    def test_company_administrator_403(self, client: TestClient, auth_headers, active_admin_user):
        resp = client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROVCA01"),
            headers=auth_headers(active_admin_user),
        )
        assert resp.status_code == 403

    def test_technician_403(self, client: TestClient, auth_headers, active_technician_user):
        resp = client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROVTE01"),
            headers=auth_headers(active_technician_user),
        )
        assert resp.status_code == 403

    def test_employee_403(self, client: TestClient, auth_headers, active_employee_user):
        resp = client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROVEM01"),
            headers=auth_headers(active_employee_user),
        )
        assert resp.status_code == 403

    def test_unauthenticated_401(self, client: TestClient):
        resp = client.post(
            "/platform/companies", json=_platform_company_payload(company_code="PROVUN01")
        )
        assert resp.status_code == 401

    def test_created_company_visible_in_list(
        self, client: TestClient, auth_headers, active_system_administrator_user
    ):
        headers = auth_headers(active_system_administrator_user)
        client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROVLIST"),
            headers=headers,
        )
        resp = client.get("/platform/companies?search=PROVLIST", headers=headers)
        codes = [c["company_code"] for c in resp.json()["data"]]
        assert "PROVLIST" in codes

    def test_created_company_visible_in_detail(
        self, client: TestClient, auth_headers, active_system_administrator_user
    ):
        headers = auth_headers(active_system_administrator_user)
        create_resp = client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROVDET1"),
            headers=headers,
        )
        new_id = create_resp.json()["data"]["id"]
        detail_resp = client.get(f"/platform/companies/{new_id}", headers=headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["company_code"] == "PROVDET1"

    def test_client_supplied_role_id_and_company_id_are_ignored_matching_self_registration(
        self, client: TestClient, auth_headers, active_system_administrator_user, company_a: Company
    ):
        """CompanyRegisterRequest has no model_config restricting extra
        fields, so Pydantic's default (extra="ignore") applies - confirmed
        by test_company_registration.py's own
        test_register_company_ignores_client_supplied_role_id/_company_id,
        which prove a 201 still comes back with these extra fields present.
        This platform route reuses that exact schema unchanged, so the
        same behavior must hold here too - a validation error here would
        be a regression against the existing, established behavior."""
        resp = client.post(
            "/platform/companies",
            json={
                **_platform_company_payload(company_code="PROVEXTRA"),
                "role_id": 999,
                "company_id": company_a.id,
            },
            headers=auth_headers(active_system_administrator_user),
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["company_code"] == "PROVEXTRA"

    def test_starter_data_matches_register_company_behavior(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        priority_repository,
        category_repository,
        location_repository,
        department_repository,
        inventory_category_repository,
    ):
        """Spot-checks that the same five kinds of starter data
        CompanyService.register_company seeds for self-registration are
        also present after platform-provisioned creation - the regression
        proof that this route truly delegates rather than reimplementing
        seeding (see CompanyService._seed_defaults for the source of truth
        these counts mirror)."""
        headers = auth_headers(active_system_administrator_user)
        create_resp = client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROVSEED"),
            headers=headers,
        )
        new_id = create_resp.json()["data"]["id"]

        assert sum(1 for p in priority_repository._by_id.values() if p.company_id == new_id) == 4
        assert sum(1 for c in category_repository._by_id.values() if c.company_id == new_id) == 5
        assert (
            sum(1 for loc in location_repository._by_id.values() if loc.company_id == new_id) == 1
        )
        assert (
            sum(1 for d in department_repository._by_id.values() if d.company_id == new_id) == 1
        )
        assert (
            sum(
                1
                for ic in inventory_category_repository._by_id.values()
                if ic.company_id == new_id
            )
            == 11
        )

    def test_existing_tenant_data_untouched(
        self,
        client: TestClient,
        auth_headers,
        active_system_administrator_user,
        active_admin_user: User,
        company_a: Company,
    ):
        headers = auth_headers(active_system_administrator_user)
        client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROVSAFE"),
            headers=headers,
        )
        # Company A's own admin can still log in, completely unaffected by
        # a brand new, unrelated company being created on the platform.
        login_resp = client.post(
            "/auth/login",
            json={
                "company_code": company_a.company_code,
                "username": active_admin_user.username,
                "password": ADMIN_PASSWORD,
            },
        )
        assert login_resp.status_code == 200

    def test_phase_8_1_and_8_3_platform_behavior_unaffected(
        self, client: TestClient, auth_headers, active_system_administrator_user
    ):
        """A lightweight regression check specific to this addition - the
        rest of this file's existing test classes already fully prove
        Phase 8.1/8.2/8.3 behavior on their own."""
        headers = auth_headers(active_system_administrator_user)
        client.post(
            "/platform/companies",
            json=_platform_company_payload(company_code="PROVREG1"),
            headers=headers,
        )
        overview_resp = client.get("/platform/overview", headers=headers)
        assert overview_resp.status_code == 200
        login_resp = client.post(
            "/platform/login",
            json={
                "username": active_system_administrator_user.username,
                "password": _PLATFORM_ADMIN_PASSWORD,
            },
        )
        assert login_resp.status_code == 200
