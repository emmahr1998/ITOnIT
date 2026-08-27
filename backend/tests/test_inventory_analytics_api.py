"""Phase C: GET /analytics/inventory, the HTTP layer over
AnalyticsService.get_inventory_analytics. Aggregation-logic correctness
(GROUP BY semantics, count_with_filters reuse) mirrors the same pattern
already proven for tickets in test_analytics_api.py - this file's job is
the HTTP contract: role gating (including the least-privilege Technician
response), response shape, and tenant isolation for inventory specifically.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.models.category import Category
from app.models.enums import (
    InventoryStatus,
    InventoryTrackingType,
    TicketInventoryUsageStatus,
    TicketStatus,
)
from app.models.inventory_category import InventoryCategory
from app.models.inventory_item import InventoryItem
from app.models.priority import Priority
from app.models.ticket import Ticket
from app.models.ticket_inventory_usage import TicketInventoryUsage
from tests.conftest import COMPANY_A_ID, COMPANY_B_ID


def _reset(repo, rows: list) -> None:
    """Full control over exactly what data a test's requests see - same
    rationale as test_analytics_api.py's _reset_tickets."""
    repo._by_id.clear()
    for row in rows:
        repo._by_id[row.id] = row
    repo._next_id = max((row.id for row in rows), default=0) + 1


def make_item(
    id_, name, tracking_type, status, category, *, stock=1, reserved=0, minimum_stock=None,
    warranty_expiration=None, company_id=COMPANY_A_ID, asset_tag=None,
) -> InventoryItem:
    item = InventoryItem(
        id=id_, company_id=company_id, inventory_category_id=category.id, name=name,
        asset_tag=asset_tag or (f"AT-{id_:03d}" if tracking_type == InventoryTrackingType.SERIALIZED else None),
        tracking_type=tracking_type, status=status, stock_quantity=stock, reserved_quantity=reserved,
        minimum_stock=minimum_stock, warranty_expiration=warranty_expiration,
    )
    item.inventory_category = category
    return item


def make_ticket_for_usage(id_, assigned_to, priority, category, company_id=COMPANY_A_ID) -> Ticket:
    t = Ticket(
        id=id_, company_id=company_id, ticket_number=f"IT-{id_:06d}", title=f"T{id_}",
        description="d", status=TicketStatus.ASSIGNED, priority_id=priority.id, category_id=category.id,
        created_by_user_id=assigned_to.id, assigned_technician_id=assigned_to.id,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    t.priority = priority
    t.category = category
    t.assigned_technician = assigned_to
    return t


def make_usage(id_, ticket, item, status, company_id=COMPANY_A_ID) -> TicketInventoryUsage:
    u = TicketInventoryUsage(
        id=id_, company_id=company_id, ticket_id=ticket.id, inventory_item_id=item.id,
        quantity=1, status=status, selected_by_user_id=ticket.assigned_technician_id,
    )
    u.ticket = ticket
    u.inventory_item = item
    return u


@pytest.fixture
def inv_category_hardware() -> InventoryCategory:
    return InventoryCategory(id=901, company_id=COMPANY_A_ID, name="Laptops", is_active=True)


@pytest.fixture
def inv_category_peripherals() -> InventoryCategory:
    return InventoryCategory(id=902, company_id=COMPANY_A_ID, name="Peripherals", is_active=True)


@pytest.fixture
def company_a_items(inv_category_hardware, inv_category_peripherals) -> list[InventoryItem]:
    soon = date.today() + timedelta(days=10)  # within the 30-day warranty window
    far = date.today() + timedelta(days=200)  # outside it
    return [
        make_item(1, "Laptop A", InventoryTrackingType.SERIALIZED, InventoryStatus.AVAILABLE, inv_category_hardware),
        make_item(2, "Laptop B", InventoryTrackingType.SERIALIZED, InventoryStatus.IN_USE, inv_category_hardware),
        make_item(
            3, "Laptop C", InventoryTrackingType.SERIALIZED, InventoryStatus.AVAILABLE,
            inv_category_hardware, warranty_expiration=soon,
        ),
        make_item(
            4, "Mice", InventoryTrackingType.BULK, InventoryStatus.AVAILABLE,
            inv_category_peripherals, stock=2, reserved=0, minimum_stock=5,  # low stock: 2-0 <= 5
        ),
        make_item(
            5, "Cables", InventoryTrackingType.BULK, InventoryStatus.AVAILABLE,
            inv_category_peripherals, stock=50, reserved=0, minimum_stock=5, warranty_expiration=far,
        ),
    ]


class TestCompanyAdministratorInventoryAnalytics:
    def test_total_items(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository, company_a_items
    ):
        _reset(inventory_item_repository, company_a_items)
        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        assert resp.status_code == 200
        assert resp.json()["data"]["total_items"] == 5

    def test_status_breakdown(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository, company_a_items
    ):
        _reset(inventory_item_repository, company_a_items)
        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        by_status = {item["status"]: item["count"] for item in resp.json()["data"]["by_status"]}
        assert by_status == {"AVAILABLE": 4, "IN_USE": 1}

    def test_category_breakdown(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository, company_a_items
    ):
        _reset(inventory_item_repository, company_a_items)
        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        by_category = {item["category"]: item["count"] for item in resp.json()["data"]["by_category"]}
        assert by_category == {"Laptops": 3, "Peripherals": 2}

    def test_low_stock_count(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository, company_a_items
    ):
        _reset(inventory_item_repository, company_a_items)
        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        assert resp.json()["data"]["low_stock_count"] == 1  # item 4 only

    def test_warranty_expiring_count(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository, company_a_items
    ):
        _reset(inventory_item_repository, company_a_items)
        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        assert resp.json()["data"]["warranty_expiring_count"] == 1  # item 3 only (10 days out)

    def test_empty_inventory(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository
    ):
        _reset(inventory_item_repository, [])
        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        data = resp.json()["data"]
        assert data["total_items"] == 0
        assert data["low_stock_count"] == 0
        assert data["warranty_expiring_count"] == 0
        assert data["by_status"] == []
        assert data["by_category"] == []

    def test_reserved_for_my_tickets_count_is_null_for_admin(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository, company_a_items
    ):
        _reset(inventory_item_repository, company_a_items)
        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        assert resp.json()["data"]["reserved_for_my_tickets_count"] is None


class TestTechnicianInventoryAnalytics:
    def test_reserved_for_my_tickets_count_correct(
        self, client: TestClient, auth_headers, active_technician_user, active_technician_user_2,
        ticket_repository, ticket_inventory_usage_repository, inventory_item_repository,
        company_a_items, low_priority, hardware_category,
    ):
        _reset(inventory_item_repository, company_a_items)
        t1 = make_ticket_for_usage(201, active_technician_user, low_priority, hardware_category)
        t2 = make_ticket_for_usage(202, active_technician_user_2, low_priority, hardware_category)
        _reset(ticket_repository, [t1, t2])
        u1 = make_usage(301, t1, company_a_items[0], TicketInventoryUsageStatus.RESERVED)
        u2 = make_usage(302, t1, company_a_items[1], TicketInventoryUsageStatus.RESERVED)
        u3 = make_usage(303, t2, company_a_items[2], TicketInventoryUsageStatus.RESERVED)  # other technician
        _reset(ticket_inventory_usage_repository, [u1, u2, u3])

        resp = client.get("/analytics/inventory", headers=auth_headers(active_technician_user))
        assert resp.status_code == 200
        assert resp.json()["data"]["reserved_for_my_tickets_count"] == 2  # u1, u2 only

    def test_other_technicians_reservations_excluded(
        self, client: TestClient, auth_headers, active_technician_user, active_technician_user_2,
        ticket_repository, ticket_inventory_usage_repository, inventory_item_repository,
        company_a_items, low_priority, hardware_category,
    ):
        _reset(inventory_item_repository, company_a_items)
        t2 = make_ticket_for_usage(202, active_technician_user_2, low_priority, hardware_category)
        _reset(ticket_repository, [t2])
        u3 = make_usage(303, t2, company_a_items[2], TicketInventoryUsageStatus.RESERVED)
        _reset(ticket_inventory_usage_repository, [u3])

        resp = client.get("/analytics/inventory", headers=auth_headers(active_technician_user))
        assert resp.json()["data"]["reserved_for_my_tickets_count"] == 0

    def test_consumed_usage_rows_excluded(
        self, client: TestClient, auth_headers, active_technician_user, ticket_repository,
        ticket_inventory_usage_repository, inventory_item_repository, company_a_items,
        low_priority, hardware_category,
    ):
        _reset(inventory_item_repository, company_a_items)
        t1 = make_ticket_for_usage(201, active_technician_user, low_priority, hardware_category)
        _reset(ticket_repository, [t1])
        consumed = make_usage(301, t1, company_a_items[0], TicketInventoryUsageStatus.CONSUMED)
        _reset(ticket_inventory_usage_repository, [consumed])

        resp = client.get("/analytics/inventory", headers=auth_headers(active_technician_user))
        assert resp.json()["data"]["reserved_for_my_tickets_count"] == 0

    def test_company_wide_fields_not_populated_for_technician(
        self, client: TestClient, auth_headers, active_technician_user, inventory_item_repository,
        ticket_inventory_usage_repository, company_a_items,
    ):
        _reset(inventory_item_repository, company_a_items)
        _reset(ticket_inventory_usage_repository, [])
        resp = client.get("/analytics/inventory", headers=auth_headers(active_technician_user))
        data = resp.json()["data"]
        assert data["total_items"] is None
        assert data["low_stock_count"] is None
        assert data["warranty_expiring_count"] is None
        assert data["by_status"] is None
        assert data["by_category"] is None
        assert data["reserved_for_my_tickets_count"] == 0


class TestAuthAndPermissions:
    def test_employee_is_forbidden(self, client: TestClient, auth_headers, active_employee_user):
        resp = client.get("/analytics/inventory", headers=auth_headers(active_employee_user))
        assert resp.status_code == 403

    def test_unauthenticated_request_is_rejected(self, client: TestClient):
        resp = client.get("/analytics/inventory")
        assert resp.status_code == 401


class TestTenantIsolation:
    def test_company_b_items_never_affect_company_a_response(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository,
        company_a_items,
    ):
        # Company B category/status deliberately overlap Company A's own
        # ("Laptops"/AVAILABLE) to prove isolation is by company_id, not by
        # these names/values happening to differ.
        b_category = InventoryCategory(id=911, company_id=COMPANY_B_ID, name="Laptops", is_active=True)
        b_item = make_item(
            101, "B Laptop", InventoryTrackingType.SERIALIZED, InventoryStatus.AVAILABLE,
            b_category, company_id=COMPANY_B_ID,
        )
        _reset(inventory_item_repository, company_a_items + [b_item])

        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        data = resp.json()["data"]
        assert data["total_items"] == 5  # not 6
        by_category = {item["category"]: item["count"] for item in data["by_category"]}
        assert by_category["Laptops"] == 3  # Company A's own 3 only
        by_status = {item["status"]: item["count"] for item in data["by_status"]}
        assert by_status["AVAILABLE"] == 4  # not 5

    def test_company_b_low_stock_and_warranty_ignored(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository, company_a_items,
    ):
        b_category = InventoryCategory(id=912, company_id=COMPANY_B_ID, name="Bulk", is_active=True)
        soon = date.today() + timedelta(days=5)
        b_low_stock = make_item(
            102, "B Cables", InventoryTrackingType.BULK, InventoryStatus.AVAILABLE, b_category,
            stock=1, reserved=0, minimum_stock=10, company_id=COMPANY_B_ID,
        )
        b_warranty = make_item(
            103, "B Warranty Item", InventoryTrackingType.SERIALIZED, InventoryStatus.AVAILABLE, b_category,
            warranty_expiration=soon, company_id=COMPANY_B_ID,
        )
        _reset(inventory_item_repository, company_a_items + [b_low_stock, b_warranty])

        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        data = resp.json()["data"]
        assert data["low_stock_count"] == 1  # Company A's own item 4 only
        assert data["warranty_expiring_count"] == 1  # Company A's own item 3 only

    def test_technician_a_reserved_count_ignores_company_b_reservations(
        self, client: TestClient, auth_headers, active_technician_user, ticket_repository,
        ticket_inventory_usage_repository, inventory_item_repository, company_a_items,
        low_priority, hardware_category, company_b_technician_user,
    ):
        _reset(inventory_item_repository, company_a_items)
        # Company B ticket+item+usage, assigned to a *different company's*
        # technician entirely - must never count toward Company A's technician.
        b_category = InventoryCategory(id=913, company_id=COMPANY_B_ID, name="Laptops", is_active=True)
        b_item = make_item(
            104, "B Item", InventoryTrackingType.SERIALIZED, InventoryStatus.AVAILABLE,
            b_category, company_id=COMPANY_B_ID,
        )
        b_priority = Priority(id=921, company_id=COMPANY_B_ID, title="Low")
        b_category_ticket = Category(id=921, company_id=COMPANY_B_ID, name="Hardware")
        b_ticket = make_ticket_for_usage(
            401, company_b_technician_user, b_priority, b_category_ticket, company_id=COMPANY_B_ID
        )
        _reset(ticket_repository, [b_ticket])
        b_usage = make_usage(501, b_ticket, b_item, TicketInventoryUsageStatus.RESERVED, company_id=COMPANY_B_ID)
        _reset(ticket_inventory_usage_repository, [b_usage])

        resp = client.get("/analytics/inventory", headers=auth_headers(active_technician_user))
        assert resp.json()["data"]["reserved_for_my_tickets_count"] == 0


class TestResponseContract:
    def test_no_orm_or_internal_ids_leak(
        self, client: TestClient, auth_headers, active_manager_user, inventory_item_repository, company_a_items
    ):
        _reset(inventory_item_repository, company_a_items)
        resp = client.get("/analytics/inventory", headers=auth_headers(active_manager_user))
        data = resp.json()["data"]
        assert set(data.keys()) == {
            "total_items", "low_stock_count", "warranty_expiring_count",
            "by_status", "by_category", "reserved_for_my_tickets_count",
        }
        for item in data["by_status"]:
            assert set(item.keys()) == {"status", "count"}
            assert isinstance(item["status"], str)
        for item in data["by_category"]:
            assert set(item.keys()) == {"category", "count"}
            assert isinstance(item["category"], str)
