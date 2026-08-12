"""Tests for Ticket <-> Inventory integration (Milestone 11): reserve,
release, consume, and remove (undo consume) of inventory against a ticket,
via TicketInventoryUsage.

TicketInventoryUsage represents the CURRENT relationship only - no
InventoryTransaction audit rows are written here (Milestone 12's job, not
this one's), and a usage row is deleted (not soft-cancelled) the moment it
stops being RESERVED-or-CONSUMED.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.models.inventory_category import InventoryCategory
from app.models.ticket import Ticket
from app.models.user import User
from tests.conftest import COMPANY_A_ID, COMPANY_B_ID, FakeInventoryCategoryRepository


def _headers(auth_headers: Callable[[User], dict[str, str]], user: User) -> dict[str, str]:
    return auth_headers(user)


# ---------------------------------------------------------------------------
# Fixtures - categories and inventory items, created the same way
# test_inventory_items.py does (categories seeded directly against the fake
# repository, items created through the real POST /inventory-items endpoint
# so InventoryItemService sets up the relationships/business rules exactly
# as production would).
# ---------------------------------------------------------------------------


@pytest.fixture
def laptop_category(
    inventory_category_repository: FakeInventoryCategoryRepository,
) -> InventoryCategory:
    return inventory_category_repository.create(
        InventoryCategory(company_id=COMPANY_A_ID, name="Laptop", is_active=True)
    )


@pytest.fixture
def cable_category(
    inventory_category_repository: FakeInventoryCategoryRepository,
) -> InventoryCategory:
    return inventory_category_repository.create(
        InventoryCategory(company_id=COMPANY_A_ID, name="Cable", is_active=True)
    )


@pytest.fixture
def deactivatable_category(
    inventory_category_repository: FakeInventoryCategoryRepository,
) -> InventoryCategory:
    return inventory_category_repository.create(
        InventoryCategory(company_id=COMPANY_A_ID, name="Docking Station", is_active=True)
    )


@pytest.fixture
def company_b_inventory_category(
    inventory_category_repository: FakeInventoryCategoryRepository,
) -> InventoryCategory:
    return inventory_category_repository.create(
        InventoryCategory(company_id=COMPANY_B_ID, name="B Laptop", is_active=True)
    )


def _create_item(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    admin_user: User,
    payload: dict,
) -> dict:
    response = client.post("/inventory-items", json=payload, headers=_headers(auth_headers, admin_user))
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest.fixture
def serialized_item(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    laptop_category: InventoryCategory,
) -> dict:
    return _create_item(
        client,
        auth_headers,
        active_admin_user,
        {
            "inventory_category_id": laptop_category.id,
            "name": "Dell Latitude 5420",
            "tracking_type": "SERIALIZED",
            "asset_tag": "LAP-1001",
        },
    )


@pytest.fixture
def second_serialized_item(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    laptop_category: InventoryCategory,
) -> dict:
    return _create_item(
        client,
        auth_headers,
        active_admin_user,
        {
            "inventory_category_id": laptop_category.id,
            "name": "Dell Latitude 5430",
            "tracking_type": "SERIALIZED",
            "asset_tag": "LAP-1002",
        },
    )


@pytest.fixture
def retired_serialized_item(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    laptop_category: InventoryCategory,
) -> dict:
    return _create_item(
        client,
        auth_headers,
        active_admin_user,
        {
            "inventory_category_id": laptop_category.id,
            "name": "Old Laptop",
            "tracking_type": "SERIALIZED",
            "asset_tag": "LAP-RETIRED",
            "status": "RETIRED",
        },
    )


@pytest.fixture
def bulk_item(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    cable_category: InventoryCategory,
) -> dict:
    return _create_item(
        client,
        auth_headers,
        active_admin_user,
        {
            "inventory_category_id": cable_category.id,
            "name": "HDMI Cable 2m",
            "tracking_type": "BULK",
            "stock_quantity": 10,
        },
    )


@pytest.fixture
def company_b_serialized_item(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_admin_user: User,
    company_b_inventory_category: InventoryCategory,
) -> dict:
    return _create_item(
        client,
        auth_headers,
        company_b_admin_user,
        {
            "inventory_category_id": company_b_inventory_category.id,
            "name": "Company B Laptop",
            "tracking_type": "SERIALIZED",
            "asset_tag": "B-LAP-1",
        },
    )


def _reserve(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    user: User,
    ticket_id: int,
    item_id: int,
    quantity: int = 1,
):
    return client.post(
        f"/tickets/{ticket_id}/inventory",
        json={"inventory_item_id": item_id, "quantity": quantity},
        headers=_headers(auth_headers, user),
    )


# ---------------------------------------------------------------------------
# Reserve - SERIALIZED
# ---------------------------------------------------------------------------


def test_reserve_serialized_succeeds_for_assigned_technician(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_technician_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, active_technician_user, assigned_ticket.id, serialized_item["id"]
    )
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["status"] == "RESERVED"
    assert body["quantity"] == 1
    assert body["inventory_item"]["id"] == serialized_item["id"]
    assert body["inventory_item"]["status"] == "RESERVED"
    assert body["selected_by"]["id"] == active_technician_user.id


def test_reserve_serialized_sets_item_status_reserved(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    check = client.get(
        f"/inventory-items/{serialized_item['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert check.json()["data"]["status"] == "RESERVED"
    assert check.json()["data"]["reserved_quantity"] == 1


def test_reserve_serialized_wrong_quantity_returns_400(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"], quantity=2
    )
    assert response.status_code == 400, response.text


# ---------------------------------------------------------------------------
# Reserve - validation: retired, inactive category, duplicate, unavailable
# ---------------------------------------------------------------------------


def test_reserve_retired_item_returns_409(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    retired_serialized_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, retired_serialized_item["id"]
    )
    assert response.status_code == 409, response.text


def test_reserve_inactive_category_returns_409(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    deactivatable_category: InventoryCategory,
) -> None:
    item = _create_item(
        client,
        auth_headers,
        active_admin_user,
        {
            "inventory_category_id": deactivatable_category.id,
            "name": "Dock",
            "tracking_type": "SERIALIZED",
            "asset_tag": "DOCK-1",
        },
    )
    patch = client.patch(
        f"/inventory-categories/{deactivatable_category.id}",
        json={"is_active": False},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert patch.status_code == 200, patch.text

    response = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, item["id"])
    assert response.status_code == 409, response.text


def test_reserve_duplicate_serialized_same_ticket_returns_409(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    first = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    assert first.status_code == 201, first.text

    second = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    assert second.status_code == 409, second.text


def test_reserve_serialized_already_reserved_by_another_ticket_returns_409(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    employee_ticket: Ticket,
    serialized_item: dict,
) -> None:
    first = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    assert first.status_code == 201, first.text

    second = _reserve(client, auth_headers, active_admin_user, employee_ticket.id, serialized_item["id"])
    assert second.status_code == 409, second.text


def test_reserve_unknown_item_returns_400(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
) -> None:
    response = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, 999999)
    assert response.status_code == 400, response.text


def test_reserve_unknown_ticket_returns_404(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    serialized_item: dict,
) -> None:
    response = _reserve(client, auth_headers, active_admin_user, 999999, serialized_item["id"])
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Reserve - BULK
# ---------------------------------------------------------------------------


def test_reserve_bulk_succeeds(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    bulk_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=4
    )
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["quantity"] == 4
    assert body["status"] == "RESERVED"

    check = client.get(
        f"/inventory-items/{bulk_item['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert check.json()["data"]["reserved_quantity"] == 4
    assert check.json()["data"]["stock_quantity"] == 10


def test_reserve_bulk_twice_on_same_ticket_merges_quantity(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    bulk_item: dict,
) -> None:
    first = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=3
    )
    assert first.status_code == 201, first.text
    first_usage_id = first.json()["data"]["id"]

    second = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=2
    )
    assert second.status_code == 201, second.text
    body = second.json()["data"]
    assert body["id"] == first_usage_id
    assert body["quantity"] == 5

    check = client.get(
        f"/inventory-items/{bulk_item['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert check.json()["data"]["reserved_quantity"] == 5


def test_reserve_bulk_more_than_available_returns_409(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    bulk_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=11
    )
    assert response.status_code == 409, response.text


def test_reserve_bulk_zero_quantity_returns_422(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    bulk_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=0
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------


def test_release_serialized_returns_item_to_available(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    usage_id = reserved.json()["data"]["id"]

    response = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/release",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 204, response.text

    check = client.get(
        f"/inventory-items/{serialized_item['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert check.json()["data"]["status"] == "AVAILABLE"
    assert check.json()["data"]["reserved_quantity"] == 0

    listing = client.get(
        f"/tickets/{assigned_ticket.id}/inventory", headers=_headers(auth_headers, active_admin_user)
    )
    assert listing.json()["data"] == []


def test_release_bulk_decrements_reserved_quantity(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    bulk_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=4
    )
    usage_id = reserved.json()["data"]["id"]

    response = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/release",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 204, response.text

    check = client.get(
        f"/inventory-items/{bulk_item['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert check.json()["data"]["reserved_quantity"] == 0
    assert check.json()["data"]["stock_quantity"] == 10


def test_release_already_consumed_returns_409(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    usage_id = reserved.json()["data"]["id"]
    client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )

    response = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/release",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 409, response.text


def test_release_unknown_usage_returns_404(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
) -> None:
    response = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/999999/release",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Consume
# ---------------------------------------------------------------------------


def test_consume_serialized_marks_item_in_use_and_sets_holder(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_technician_user: User,
    assigned_ticket: Ticket,
    active_employee_user: User,
    serialized_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_technician_user, assigned_ticket.id, serialized_item["id"]
    )
    usage_id = reserved.json()["data"]["id"]

    response = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_technician_user),
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == "CONSUMED"
    assert body["inventory_item"]["status"] == "IN_USE"
    assert body["inventory_item"]["current_holder"]["id"] == active_employee_user.id
    assert body["inventory_item"]["reserved_quantity"] == 0


def test_consume_bulk_decrements_stock_and_reserved(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    bulk_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=4
    )
    usage_id = reserved.json()["data"]["id"]

    response = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["inventory_item"]["stock_quantity"] == 6
    assert body["inventory_item"]["reserved_quantity"] == 0


def test_consume_already_consumed_returns_409(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    usage_id = reserved.json()["data"]["id"]
    client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )

    response = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 409, response.text


# ---------------------------------------------------------------------------
# Remove (undo consume) - Company Administrator only
# ---------------------------------------------------------------------------


def test_remove_undoes_consumed_serialized(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    usage_id = reserved.json()["data"]["id"]
    client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )

    response = client.delete(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 204, response.text

    check = client.get(
        f"/inventory-items/{serialized_item['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert check.json()["data"]["status"] == "AVAILABLE"
    assert check.json()["data"]["current_holder"] is None


def test_remove_undoes_consumed_bulk_restores_stock(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    bulk_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=4
    )
    usage_id = reserved.json()["data"]["id"]
    client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )

    response = client.delete(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 204, response.text

    check = client.get(
        f"/inventory-items/{bulk_item['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert check.json()["data"]["stock_quantity"] == 10
    assert check.json()["data"]["reserved_quantity"] == 0


def test_remove_forbidden_for_technician(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    active_technician_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    usage_id = reserved.json()["data"]["id"]
    client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )

    response = client.delete(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}",
        headers=_headers(auth_headers, active_technician_user),
    )
    assert response.status_code == 403, response.text


def test_remove_reserved_row_returns_409(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    usage_id = reserved.json()["data"]["id"]

    response = client.delete(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 409, response.text


# ---------------------------------------------------------------------------
# List / multiple items per ticket
# ---------------------------------------------------------------------------


def test_list_returns_multiple_attached_items(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
    second_serialized_item: dict,
    bulk_item: dict,
) -> None:
    _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, second_serialized_item["id"])
    _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=2)

    response = client.get(
        f"/tickets/{assigned_ticket.id}/inventory", headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert len(body) == 3
    item_ids = {row["inventory_item"]["id"] for row in body}
    assert item_ids == {serialized_item["id"], second_serialized_item["id"], bulk_item["id"]}


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_employee_forbidden_from_listing(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_employee_user: User,
    employee_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{employee_ticket.id}/inventory", headers=_headers(auth_headers, active_employee_user)
    )
    assert response.status_code == 403, response.text


def test_employee_forbidden_from_reserving_even_own_ticket(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_employee_user: User,
    employee_ticket: Ticket,
    serialized_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, active_employee_user, employee_ticket.id, serialized_item["id"]
    )
    assert response.status_code == 403, response.text


def test_unassigned_technician_forbidden(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_technician_user_2: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, active_technician_user_2, assigned_ticket.id, serialized_item["id"]
    )
    assert response.status_code == 403, response.text


def test_assigned_technician_can_reserve_release_consume(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_technician_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
    second_serialized_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_technician_user, assigned_ticket.id, serialized_item["id"]
    )
    assert reserved.status_code == 201
    usage_id = reserved.json()["data"]["id"]

    release = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/release",
        headers=_headers(auth_headers, active_technician_user),
    )
    assert release.status_code == 204

    reserved_2 = _reserve(
        client, auth_headers, active_technician_user, assigned_ticket.id, second_serialized_item["id"]
    )
    usage_id_2 = reserved_2.json()["data"]["id"]
    consume = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id_2}/consume",
        headers=_headers(auth_headers, active_technician_user),
    )
    assert consume.status_code == 200


def test_company_administrator_can_act_on_any_ticket(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    employee_ticket: Ticket,
    serialized_item: dict,
) -> None:
    response = _reserve(client, auth_headers, active_admin_user, employee_ticket.id, serialized_item["id"])
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_cannot_reserve_company_b_item_on_company_a_ticket(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    company_b_serialized_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, company_b_serialized_item["id"]
    )
    assert response.status_code == 400, response.text


def test_company_b_admin_cannot_reserve_against_company_a_ticket(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_admin_user: User,
    assigned_ticket: Ticket,
    company_b_serialized_item: dict,
) -> None:
    response = _reserve(
        client, auth_headers, company_b_admin_user, assigned_ticket.id, company_b_serialized_item["id"]
    )
    assert response.status_code == 404, response.text


def test_company_b_admin_cannot_list_company_a_ticket_inventory(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    company_b_admin_user: User,
    assigned_ticket: Ticket,
) -> None:
    response = client.get(
        f"/tickets/{assigned_ticket.id}/inventory", headers=_headers(auth_headers, company_b_admin_user)
    )
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Ticket deletion cleanup
# ---------------------------------------------------------------------------


def test_deleting_ticket_releases_reserved_inventory(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    serialized_item: dict,
) -> None:
    _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])

    response = client.delete(
        f"/tickets/{assigned_ticket.id}", headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 204, response.text

    check = client.get(
        f"/inventory-items/{serialized_item['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert check.json()["data"]["status"] == "AVAILABLE"
    assert check.json()["data"]["reserved_quantity"] == 0


def test_deleting_ticket_reverts_consumed_inventory(
    client: TestClient,
    auth_headers: Callable[[User], dict[str, str]],
    active_admin_user: User,
    assigned_ticket: Ticket,
    bulk_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=3
    )
    usage_id = reserved.json()["data"]["id"]
    client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )

    response = client.delete(
        f"/tickets/{assigned_ticket.id}", headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 204, response.text

    check = client.get(
        f"/inventory-items/{bulk_item['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert check.json()["data"]["stock_quantity"] == 10
    assert check.json()["data"]["reserved_quantity"] == 0
