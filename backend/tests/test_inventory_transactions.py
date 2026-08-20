"""Tests for InventoryTransaction (Phase 12.1) - the permanent, append-only
audit trail for InventoryItem changes.

Covers: every transaction type, create/edit (including the dedicated
STOCK_ADJUSTED/STATUS_CHANGED/HOLDER_CHANGED/LOCATION_CHANGED carve-outs
vs. the generic EDITED fallback), reserve/release/consume/consume-undo,
ticket-deletion cleanup, tenant isolation, permissions, append-only
behavior, and atomic-rollback structure.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.models.inventory_category import InventoryCategory
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.inventory_transaction import InventoryTransactionRepository
from app.schemas.inventory_item import InventoryItemCreate
from app.services.inventory_item_service import InventoryItemService
from app.services.inventory_transaction_service import InventoryTransactionService
from app.services.ticket_inventory_service import TicketInventoryService
from tests.conftest import (
    COMPANY_A_ID,
    COMPANY_B_ID,
    FakeInventoryCategoryRepository,
    FakeInventoryItemRepository,
    FakeTicketInventoryUsageRepository,
    FakeTicketRepository,
    FakeUserRepository,
)


def _headers(auth_headers: Callable[[User], dict[str, str]], user: User) -> dict[str, str]:
    return auth_headers(user)


# ---------------------------------------------------------------------------
# Fixtures - same conventions as test_ticket_inventory.py
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
            "asset_tag": "TX-LAP-1",
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
def company_b_item(
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
            "asset_tag": "B-TX-LAP-1",
        },
    )


def _transactions_for_item(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], user: User, item_id: int
) -> list[dict]:
    response = client.get(
        f"/inventory-items/{item_id}/transactions", headers=_headers(auth_headers, user)
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


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
# CREATED
# ---------------------------------------------------------------------------


def test_create_serialized_item_writes_created_transaction(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    assert len(transactions) == 1
    tx = transactions[0]
    assert tx["transaction_type"] == "CREATED"
    assert tx["quantity_delta"] == 1
    assert tx["ticket"] is None
    assert tx["performed_by"]["id"] == active_admin_user.id
    assert "SERIALIZED" in tx["notes"]


def test_create_bulk_item_writes_created_transaction_with_stock_quantity_delta(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    bulk_item: dict,
) -> None:
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, bulk_item["id"])
    assert len(transactions) == 1
    assert transactions[0]["transaction_type"] == "CREATED"
    assert transactions[0]["quantity_delta"] == 10


# ---------------------------------------------------------------------------
# EDITED (generic) vs. dedicated STOCK_ADJUSTED/STATUS_CHANGED/
# HOLDER_CHANGED/LOCATION_CHANGED
# ---------------------------------------------------------------------------


def test_edit_simple_field_writes_edited_transaction(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    response = client.patch(
        f"/inventory-items/{serialized_item['id']}",
        json={"manufacturer": "Dell"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    edited = [t for t in transactions if t["transaction_type"] == "EDITED"]
    assert len(edited) == 1
    assert edited[0]["field_name"] == "manufacturer"
    assert edited[0]["old_value"] is None
    assert edited[0]["new_value"] == "Dell"


def test_edit_multiple_fields_writes_one_row_per_changed_field(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    response = client.patch(
        f"/inventory-items/{serialized_item['id']}",
        json={"manufacturer": "Dell", "model": "Latitude 5420", "supplier": "CDW"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    edited_fields = {t["field_name"] for t in transactions if t["transaction_type"] == "EDITED"}
    assert edited_fields == {"manufacturer", "model", "supplier"}


def test_edit_with_unchanged_value_writes_no_transaction(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    # name is already "Dell Latitude 5420" - resubmitting the same value
    # should not produce a spurious EDITED row.
    response = client.patch(
        f"/inventory-items/{serialized_item['id']}",
        json={"name": serialized_item["name"]},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    assert len(transactions) == 1  # only the original CREATED row
    assert transactions[0]["transaction_type"] == "CREATED"


def test_edit_status_writes_status_changed_not_edited(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    response = client.patch(
        f"/inventory-items/{serialized_item['id']}",
        json={"status": "IN_REPAIR"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    status_rows = [t for t in transactions if t["transaction_type"] == "STATUS_CHANGED"]
    assert len(status_rows) == 1
    assert status_rows[0]["field_name"] == "status"
    assert status_rows[0]["old_value"] == "AVAILABLE"
    assert status_rows[0]["new_value"] == "IN_REPAIR"
    assert not any(t["transaction_type"] == "EDITED" for t in transactions)


def test_retiring_item_writes_status_changed_not_a_separate_retired_type(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    response = client.patch(
        f"/inventory-items/{serialized_item['id']}",
        json={"status": "RETIRED"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    status_rows = [t for t in transactions if t["transaction_type"] == "STATUS_CHANGED"]
    assert len(status_rows) == 1
    assert status_rows[0]["new_value"] == "RETIRED"


def test_edit_holder_writes_holder_changed(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    active_employee_user: User, serialized_item: dict,
) -> None:
    response = client.patch(
        f"/inventory-items/{serialized_item['id']}",
        json={"current_holder_user_id": active_employee_user.id},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    holder_rows = [t for t in transactions if t["transaction_type"] == "HOLDER_CHANGED"]
    assert len(holder_rows) == 1
    assert holder_rows[0]["old_value"] is None
    assert holder_rows[0]["new_value"] == f"{active_employee_user.first_name} {active_employee_user.last_name}"


def test_edit_location_writes_location_changed(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    head_office_location, serialized_item: dict,
) -> None:
    response = client.patch(
        f"/inventory-items/{serialized_item['id']}",
        json={"current_location_id": head_office_location.id},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    location_rows = [t for t in transactions if t["transaction_type"] == "LOCATION_CHANGED"]
    assert len(location_rows) == 1
    assert location_rows[0]["new_value"] == head_office_location.title


def test_edit_stock_quantity_writes_stock_adjusted(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    bulk_item: dict,
) -> None:
    response = client.patch(
        f"/inventory-items/{bulk_item['id']}",
        json={"stock_quantity": 15},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, bulk_item["id"])
    stock_rows = [t for t in transactions if t["transaction_type"] == "STOCK_ADJUSTED"]
    assert len(stock_rows) == 1
    assert stock_rows[0]["quantity_delta"] == 5
    assert stock_rows[0]["old_value"] == "10"
    assert stock_rows[0]["new_value"] == "15"


def test_edit_stock_quantity_down_writes_negative_delta(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    bulk_item: dict,
) -> None:
    response = client.patch(
        f"/inventory-items/{bulk_item['id']}",
        json={"stock_quantity": 4},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200, response.text
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, bulk_item["id"])
    stock_rows = [t for t in transactions if t["transaction_type"] == "STOCK_ADJUSTED"]
    assert stock_rows[0]["quantity_delta"] == -6


# ---------------------------------------------------------------------------
# RESERVED / RELEASED / CONSUMED / CONSUME_UNDONE (ticket workflow)
# ---------------------------------------------------------------------------


def test_reserve_serialized_writes_reserved_transaction(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    assert reserved.status_code == 201, reserved.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    reserved_rows = [t for t in transactions if t["transaction_type"] == "RESERVED"]
    assert len(reserved_rows) == 1
    assert reserved_rows[0]["quantity_delta"] == 1
    assert reserved_rows[0]["ticket"]["id"] == assigned_ticket.id
    assert reserved_rows[0]["field_name"] == "status"
    assert reserved_rows[0]["old_value"] == "AVAILABLE"
    assert reserved_rows[0]["new_value"] == "RESERVED"


def test_reserve_bulk_writes_reserved_transaction_with_quantity_delta(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, bulk_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=4
    )
    assert reserved.status_code == 201, reserved.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, bulk_item["id"])
    reserved_rows = [t for t in transactions if t["transaction_type"] == "RESERVED"]
    assert len(reserved_rows) == 1
    assert reserved_rows[0]["quantity_delta"] == 4
    assert reserved_rows[0]["field_name"] is None


def test_reserve_bulk_merge_writes_second_reserved_transaction_with_incremental_delta_only(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, bulk_item: dict,
) -> None:
    _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=3)
    _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=2)

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, bulk_item["id"])
    reserved_rows = [t for t in transactions if t["transaction_type"] == "RESERVED"]
    assert len(reserved_rows) == 2
    deltas = sorted(t["quantity_delta"] for t in reserved_rows)
    assert deltas == [2, 3]  # each row reflects only that call's incremental amount


def test_release_serialized_writes_released_transaction(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    usage_id = reserved.json()["data"]["id"]

    release = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/release",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert release.status_code == 204, release.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    released_rows = [t for t in transactions if t["transaction_type"] == "RELEASED"]
    assert len(released_rows) == 1
    assert released_rows[0]["quantity_delta"] == -1
    assert released_rows[0]["old_value"] == "RESERVED"
    assert released_rows[0]["new_value"] == "AVAILABLE"


def test_release_bulk_writes_released_transaction(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, bulk_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=4
    )
    usage_id = reserved.json()["data"]["id"]

    release = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/release",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert release.status_code == 204, release.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, bulk_item["id"])
    released_rows = [t for t in transactions if t["transaction_type"] == "RELEASED"]
    assert released_rows[0]["quantity_delta"] == -4


def test_consume_serialized_writes_consumed_transaction_with_notes(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    active_employee_user: User, assigned_ticket: Ticket, serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    usage_id = reserved.json()["data"]["id"]

    consume = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert consume.status_code == 200, consume.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    consumed_rows = [t for t in transactions if t["transaction_type"] == "CONSUMED"]
    assert len(consumed_rows) == 1
    assert consumed_rows[0]["quantity_delta"] is None
    assert "IN_USE" in consumed_rows[0]["notes"]
    assert consumed_rows[0]["ticket"]["id"] == assigned_ticket.id


def test_consume_bulk_writes_consumed_transaction_with_quantity_delta(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, bulk_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=4
    )
    usage_id = reserved.json()["data"]["id"]

    consume = client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert consume.status_code == 200, consume.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, bulk_item["id"])
    consumed_rows = [t for t in transactions if t["transaction_type"] == "CONSUMED"]
    assert consumed_rows[0]["quantity_delta"] == -4


def test_remove_undoes_consumed_serialized_writes_consume_undone(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, serialized_item: dict,
) -> None:
    reserved = _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])
    usage_id = reserved.json()["data"]["id"]
    client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )

    remove = client.delete(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert remove.status_code == 204, remove.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    undone_rows = [t for t in transactions if t["transaction_type"] == "CONSUME_UNDONE"]
    assert len(undone_rows) == 1
    assert undone_rows[0]["quantity_delta"] is None
    assert "AVAILABLE" in undone_rows[0]["notes"]


def test_remove_undoes_consumed_bulk_writes_consume_undone_with_quantity_delta(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, bulk_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=4
    )
    usage_id = reserved.json()["data"]["id"]
    client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )

    remove = client.delete(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert remove.status_code == 204, remove.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, bulk_item["id"])
    undone_rows = [t for t in transactions if t["transaction_type"] == "CONSUME_UNDONE"]
    assert undone_rows[0]["quantity_delta"] == 4


# ---------------------------------------------------------------------------
# Ticket deletion cleanup
# ---------------------------------------------------------------------------


def test_deleting_ticket_with_reserved_item_writes_released_transaction(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, serialized_item: dict,
) -> None:
    _reserve(client, auth_headers, active_admin_user, assigned_ticket.id, serialized_item["id"])

    delete = client.delete(
        f"/tickets/{assigned_ticket.id}", headers=_headers(auth_headers, active_admin_user)
    )
    assert delete.status_code == 204, delete.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    released_rows = [t for t in transactions if t["transaction_type"] == "RELEASED"]
    assert len(released_rows) == 1
    assert "deleted" in released_rows[0]["notes"]
    assert assigned_ticket.ticket_number in released_rows[0]["notes"]
    assert released_rows[0]["performed_by"]["id"] == active_admin_user.id


def test_deleting_ticket_with_consumed_item_writes_consume_undone_transaction(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    assigned_ticket: Ticket, bulk_item: dict,
) -> None:
    reserved = _reserve(
        client, auth_headers, active_admin_user, assigned_ticket.id, bulk_item["id"], quantity=3
    )
    usage_id = reserved.json()["data"]["id"]
    client.patch(
        f"/tickets/{assigned_ticket.id}/inventory/{usage_id}/consume",
        headers=_headers(auth_headers, active_admin_user),
    )

    delete = client.delete(
        f"/tickets/{assigned_ticket.id}", headers=_headers(auth_headers, active_admin_user)
    )
    assert delete.status_code == 204, delete.text

    transactions = _transactions_for_item(client, auth_headers, active_admin_user, bulk_item["id"])
    undone_rows = [t for t in transactions if t["transaction_type"] == "CONSUME_UNDONE"]
    assert len(undone_rows) == 1
    assert undone_rows[0]["quantity_delta"] == 3
    assert "deleted" in undone_rows[0]["notes"]


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_company_b_cannot_view_company_a_item_transactions(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], company_b_admin_user: User,
    serialized_item: dict,
) -> None:
    response = client.get(
        f"/inventory-items/{serialized_item['id']}/transactions",
        headers=_headers(auth_headers, company_b_admin_user),
    )
    assert response.status_code == 404, response.text


def test_company_wide_transactions_never_leak_across_companies(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    company_b_admin_user: User, serialized_item: dict, company_b_item: dict,
) -> None:
    company_a_response = client.get(
        "/inventory-transactions", headers=_headers(auth_headers, active_admin_user)
    )
    assert company_a_response.status_code == 200
    company_a_item_ids = {t["inventory_item"]["id"] for t in company_a_response.json()["data"]}
    assert company_b_item["id"] not in company_a_item_ids
    assert serialized_item["id"] in company_a_item_ids

    company_b_response = client.get(
        "/inventory-transactions", headers=_headers(auth_headers, company_b_admin_user)
    )
    assert company_b_response.status_code == 200
    company_b_item_ids = {t["inventory_item"]["id"] for t in company_b_response.json()["data"]}
    assert serialized_item["id"] not in company_b_item_ids
    assert company_b_item["id"] in company_b_item_ids


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_company_administrator_can_view_item_transactions(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    response = client.get(
        f"/inventory-items/{serialized_item['id']}/transactions",
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200


def test_technician_can_view_item_transactions(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_technician_user: User,
    serialized_item: dict,
) -> None:
    response = client.get(
        f"/inventory-items/{serialized_item['id']}/transactions",
        headers=_headers(auth_headers, active_technician_user),
    )
    assert response.status_code == 200


def test_employee_forbidden_from_item_transactions(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_employee_user: User,
    serialized_item: dict,
) -> None:
    response = client.get(
        f"/inventory-items/{serialized_item['id']}/transactions",
        headers=_headers(auth_headers, active_employee_user),
    )
    assert response.status_code == 403


def test_company_administrator_can_view_company_wide_transactions(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    response = client.get("/inventory-transactions", headers=_headers(auth_headers, active_admin_user))
    assert response.status_code == 200


def test_technician_forbidden_from_company_wide_transactions(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_technician_user: User,
    serialized_item: dict,
) -> None:
    response = client.get(
        "/inventory-transactions", headers=_headers(auth_headers, active_technician_user)
    )
    assert response.status_code == 403


def test_employee_forbidden_from_company_wide_transactions(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_employee_user: User,
    serialized_item: dict,
) -> None:
    response = client.get(
        "/inventory-transactions", headers=_headers(auth_headers, active_employee_user)
    )
    assert response.status_code == 403


def test_company_wide_transactions_filters_by_type(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    response = client.get(
        "/inventory-transactions",
        params={"transaction_type": "CREATED"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200
    assert all(t["transaction_type"] == "CREATED" for t in response.json()["data"])


# ---------------------------------------------------------------------------
# Append-only guarantee
# ---------------------------------------------------------------------------


def test_no_post_route_exists_for_item_transactions(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    response = client.post(
        f"/inventory-items/{serialized_item['id']}/transactions",
        json={},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code in (404, 405)


def test_no_post_route_exists_for_company_wide_transactions(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
) -> None:
    response = client.post(
        "/inventory-transactions", json={}, headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code in (404, 405)


def test_no_patch_or_delete_route_exists_for_a_transaction(
    client: TestClient, auth_headers: Callable[[User], dict[str, str]], active_admin_user: User,
    serialized_item: dict,
) -> None:
    transactions = _transactions_for_item(client, auth_headers, active_admin_user, serialized_item["id"])
    transaction_id = transactions[0]["id"]
    patch_response = client.patch(
        f"/inventory-transactions/{transaction_id}",
        json={},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert patch_response.status_code in (404, 405)
    delete_response = client.delete(
        f"/inventory-transactions/{transaction_id}", headers=_headers(auth_headers, active_admin_user)
    )
    assert delete_response.status_code in (404, 405)


def test_repository_update_raises() -> None:
    # BaseRepository provides update()/delete() by inheritance to every
    # repository in this codebase, so InventoryTransactionRepository
    # overrides both to raise - this is what actually makes append-only
    # structural rather than just "nobody happens to call it".
    repo = InventoryTransactionRepository(db=None, company_id=COMPANY_A_ID)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        repo.update(None)  # type: ignore[arg-type]


def test_repository_delete_raises() -> None:
    repo = InventoryTransactionRepository(db=None, company_id=COMPANY_A_ID)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        repo.delete(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Atomic rollback - service-level, mirrors test_tickets.py's
# test_create_ticket_new_retries_ticket_number_on_integrity_error pattern
# (direct service construction with a deliberately broken collaborator).
# ---------------------------------------------------------------------------


class _RaisingTransactionRepository:
    """A transaction repository whose create() always fails, to prove the
    orchestrating service never reaches its own commit() when the audit
    write fails - see InventoryTransactionService's docstring on why this
    makes the whole operation atomic."""

    def create(self, obj):
        raise RuntimeError("simulated audit-log write failure")


class _TrackingSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_create_item_never_commits_if_transaction_write_fails(
    laptop_category: InventoryCategory,
    active_admin_user: User,
) -> None:
    session = _TrackingSession()
    broken_transaction_service = InventoryTransactionService(
        db=session, company_id=COMPANY_A_ID, transaction_repository=_RaisingTransactionRepository()
    )
    service = InventoryItemService(
        db=session,
        company_id=COMPANY_A_ID,
        item_repository=FakeInventoryItemRepository(),
        category_repository=FakeInventoryCategoryRepository([laptop_category], company_id=COMPANY_A_ID),
        user_repository=FakeUserRepository([active_admin_user]).scoped(COMPANY_A_ID),
        inventory_transaction_service=broken_transaction_service,
    )
    # location_repository is left at its default (a real LocationRepository
    # wrapping the tracking session) - harmless, since create_item never
    # touches it unless current_location_id is in the payload, which this
    # one omits.
    payload = InventoryItemCreate(
        inventory_category_id=laptop_category.id,
        name="Doomed Laptop",
        tracking_type="SERIALIZED",
        asset_tag="DOOMED-1",
    )

    with pytest.raises(RuntimeError):
        service.create_item(payload, active_admin_user)

    assert session.commit_calls == 0


def test_reserve_never_commits_if_transaction_write_fails(
    assigned_ticket: Ticket,
    active_admin_user: User,
    active_technician_user: User,
    serialized_item: dict,
    inventory_item_repository: FakeInventoryItemRepository,
    ticket_repository: FakeTicketRepository,
) -> None:
    session = _TrackingSession()
    broken_transaction_service = InventoryTransactionService(
        db=session, company_id=COMPANY_A_ID, transaction_repository=_RaisingTransactionRepository()
    )
    service = TicketInventoryService(
        db=session,
        company_id=COMPANY_A_ID,
        usage_repository=FakeTicketInventoryUsageRepository(company_id=COMPANY_A_ID),
        item_repository=inventory_item_repository,
        ticket_repository=ticket_repository,
        inventory_transaction_service=broken_transaction_service,
    )
    inventory_item_repository.company_id = COMPANY_A_ID
    ticket_repository.company_id = COMPANY_A_ID

    with pytest.raises(RuntimeError):
        service.reserve(active_admin_user, assigned_ticket.id, serialized_item["id"], 1)

    assert session.commit_calls == 0
