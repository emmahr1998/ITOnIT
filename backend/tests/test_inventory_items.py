"""Tests for InventoryItem CRUD, search, filtering, sorting, pagination,
and SERIALIZED/BULK validation (Phase 10.2). No DELETE endpoint exists;
retirement is via PATCH status=RETIRED.

Service-level business-rule validation (InventoryItemService.
_validate_business_rules) mirrors the eight database CHECK constraints
from Phase 10.1 exactly - those constraints were already verified directly
against the real database in that phase (16/16 valid+invalid cases
passed) and are unchanged here; this file proves the *service* rejects the
same invalid combinations before ever reaching the database.
"""

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models.inventory_category import InventoryCategory
from app.models.user import User
from tests.conftest import (
    COMPANY_A_ID,
    COMPANY_B_ID,
    FakeInventoryCategoryRepository,
)


def _headers(auth_headers: Callable[[User], dict[str, str]], user: User) -> dict[str, str]:
    return auth_headers(user)


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
def inactive_category(
    inventory_category_repository: FakeInventoryCategoryRepository,
) -> InventoryCategory:
    return inventory_category_repository.create(
        InventoryCategory(company_id=COMPANY_A_ID, name="Retired Type", is_active=False)
    )


@pytest.fixture
def company_b_inventory_category(
    inventory_category_repository: FakeInventoryCategoryRepository,
) -> InventoryCategory:
    return inventory_category_repository.create(
        InventoryCategory(company_id=COMPANY_B_ID, name="B Laptop", is_active=True)
    )


def _serialized_payload(category_id: int, **overrides: object) -> dict:
    payload = {
        "inventory_category_id": category_id,
        "name": "Dell Latitude 5420",
        "tracking_type": "SERIALIZED",
        "asset_tag": "LAP-0001",
    }
    payload.update(overrides)
    return payload


def _bulk_payload(category_id: int, **overrides: object) -> dict:
    payload = {
        "inventory_category_id": category_id,
        "name": "HDMI Cable 2m",
        "tracking_type": "BULK",
        "stock_quantity": 50,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Create - SERIALIZED / BULK happy paths
# ---------------------------------------------------------------------------


def test_create_serialized_item_succeeds(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["tracking_type"] == "SERIALIZED"
    assert body["asset_tag"] == "LAP-0001"
    assert body["stock_quantity"] == 1
    assert body["reserved_quantity"] == 0
    assert body["status"] == "AVAILABLE"
    assert body["inventory_category"]["id"] == laptop_category.id


def test_create_serialized_item_defaults_stock_quantity_to_one(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    payload = _serialized_payload(laptop_category.id)
    response = client.post(
        "/inventory-items", json=payload, headers=_headers(auth_headers, active_admin_user)
    )
    assert response.json()["data"]["stock_quantity"] == 1


def test_create_bulk_item_succeeds(
    client: TestClient, auth_headers, active_admin_user: User, cable_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_bulk_payload(cable_category.id, minimum_stock=10),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["tracking_type"] == "BULK"
    assert body["stock_quantity"] == 50
    assert body["reserved_quantity"] == 0
    assert body["asset_tag"] is None
    assert body["minimum_stock"] == 10


def test_create_item_with_full_metadata(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    payload = _serialized_payload(
        laptop_category.id,
        asset_tag="LAP-META-1",
        manufacturer="Dell",
        model="Latitude 5420",
        serial_number="SN12345",
        condition="GOOD",
        purchase_date="2025-01-15",
        warranty_expiration="2028-01-15",
        supplier="Acme Supplies",
        purchase_cost="1299.99",
        invoice_number="INV-0042",
        image_path="inventory/lap-meta-1.jpg",
        notes="Assigned during onboarding.",
    )
    response = client.post(
        "/inventory-items", json=payload, headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["manufacturer"] == "Dell"
    assert body["condition"] == "GOOD"
    assert body["purchase_cost"] == "1299.99"
    assert body["invoice_number"] == "INV-0042"
    assert body["image_path"] == "inventory/lap-meta-1.jpg"


# ---------------------------------------------------------------------------
# Fetch / list
# ---------------------------------------------------------------------------


def test_get_inventory_item_by_id(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers
    )
    item_id = created.json()["data"]["id"]

    response = client.get(f"/inventory-items/{item_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["id"] == item_id


def test_get_inventory_item_not_found(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    response = client.get(
        "/inventory-items/999999", headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 404


def test_list_inventory_items(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    client.post("/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers)
    client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, asset_tag="LAP-0002"),
        headers=headers,
    )

    response = client.get("/inventory-items", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
    assert "2 of 2" in response.json()["msg"]


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------


def test_patch_inventory_item_rename(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers
    )
    item_id = created.json()["data"]["id"]

    response = client.patch(
        f"/inventory-items/{item_id}", json={"name": "Dell Latitude 5420 (renamed)"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Dell Latitude 5420 (renamed)"


def test_patch_inventory_item_reassign_category(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    laptop_category: InventoryCategory,
    cable_category: InventoryCategory,
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-items", json=_bulk_payload(laptop_category.id), headers=headers
    )
    item_id = created.json()["data"]["id"]

    response = client.patch(
        f"/inventory-items/{item_id}",
        json={"inventory_category_id": cable_category.id},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["inventory_category"]["id"] == cable_category.id


def test_patch_inventory_item_clear_location(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    laptop_category: InventoryCategory,
    head_office_location,
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-items",
        json=_serialized_payload(
            laptop_category.id, current_location_id=head_office_location.id
        ),
        headers=headers,
    )
    item_id = created.json()["data"]["id"]
    assert created.json()["data"]["current_location"]["id"] == head_office_location.id

    response = client.patch(
        f"/inventory-items/{item_id}", json={"current_location_id": None}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["current_location"] is None


def test_retire_item_via_status(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers
    )
    item_id = created.json()["data"]["id"]

    response = client.patch(
        f"/inventory-items/{item_id}", json={"status": "RETIRED"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "RETIRED"


def test_patch_inventory_item_not_found(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    response = client.patch(
        "/inventory-items/999999",
        json={"name": "Whatever"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@pytest.fixture
def searchable_item(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> dict:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-items",
        json=_serialized_payload(
            laptop_category.id,
            name="Dell Latitude 5420",
            asset_tag="SEARCHTAG1",
            manufacturer="Dell",
            model="Latitude 5420",
            serial_number="SEARCHSERIAL1",
            supplier="Acme Supplies",
            invoice_number="SEARCHINV1",
        ),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]


@pytest.mark.parametrize(
    "term",
    ["dell latitude", "SEARCHTAG1", "searchserial1", "Acme", "SEARCHINV1", "5420"],
)
def test_search_matches_across_fields(
    client: TestClient, auth_headers, active_admin_user: User, searchable_item: dict, term: str
) -> None:
    response = client.get(
        "/inventory-items",
        params={"search": term},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 200
    ids = [i["id"] for i in response.json()["data"]]
    assert searchable_item["id"] in ids


def test_search_no_match_returns_empty(
    client: TestClient, auth_headers, active_admin_user: User, searchable_item: dict
) -> None:
    response = client.get(
        "/inventory-items",
        params={"search": "nonexistent-needle"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.json()["data"] == []


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_filter_by_inventory_category_id(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    laptop_category: InventoryCategory,
    cable_category: InventoryCategory,
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    laptop = client.post(
        "/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers
    ).json()["data"]
    client.post("/inventory-items", json=_bulk_payload(cable_category.id), headers=headers)

    response = client.get(
        "/inventory-items", params={"inventory_category_id": laptop_category.id}, headers=headers
    )
    ids = [i["id"] for i in response.json()["data"]]
    assert ids == [laptop["id"]]


def test_filter_by_tracking_type(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    client.post("/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers)
    bulk = client.post(
        "/inventory-items", json=_bulk_payload(laptop_category.id), headers=headers
    ).json()["data"]

    response = client.get(
        "/inventory-items", params={"tracking_type": "BULK"}, headers=headers
    )
    ids = [i["id"] for i in response.json()["data"]]
    assert ids == [bulk["id"]]


def test_filter_by_status(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers
    ).json()["data"]
    client.patch(f"/inventory-items/{created['id']}", json={"status": "RETIRED"}, headers=headers)
    client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, asset_tag="LAP-OTHER"),
        headers=headers,
    )

    response = client.get("/inventory-items", params={"status": "RETIRED"}, headers=headers)
    ids = [i["id"] for i in response.json()["data"]]
    assert ids == [created["id"]]


def test_filter_by_condition(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    damaged = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, condition="DAMAGED"),
        headers=headers,
    ).json()["data"]
    client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, asset_tag="LAP-GOOD", condition="GOOD"),
        headers=headers,
    )

    response = client.get("/inventory-items", params={"condition": "DAMAGED"}, headers=headers)
    ids = [i["id"] for i in response.json()["data"]]
    assert ids == [damaged["id"]]


def test_filter_by_current_location_id(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    laptop_category: InventoryCategory,
    head_office_location,
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    located = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, current_location_id=head_office_location.id),
        headers=headers,
    ).json()["data"]
    client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, asset_tag="LAP-NOLOC"),
        headers=headers,
    )

    response = client.get(
        "/inventory-items",
        params={"current_location_id": head_office_location.id},
        headers=headers,
    )
    ids = [i["id"] for i in response.json()["data"]]
    assert ids == [located["id"]]


def test_filter_by_current_holder_user_id(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    laptop_category: InventoryCategory,
    active_employee_user: User,
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    held = client.post(
        "/inventory-items",
        json=_serialized_payload(
            laptop_category.id, current_holder_user_id=active_employee_user.id, status="IN_USE"
        ),
        headers=headers,
    ).json()["data"]
    client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, asset_tag="LAP-UNHELD"),
        headers=headers,
    )

    response = client.get(
        "/inventory-items",
        params={"current_holder_user_id": active_employee_user.id},
        headers=headers,
    )
    ids = [i["id"] for i in response.json()["data"]]
    assert ids == [held["id"]]


def test_filter_by_manufacturer_and_model(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    dell = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, manufacturer="Dell", model="Latitude 5420"),
        headers=headers,
    ).json()["data"]
    client.post(
        "/inventory-items",
        json=_serialized_payload(
            laptop_category.id, asset_tag="LAP-HP", manufacturer="HP", model="EliteBook"
        ),
        headers=headers,
    )

    response = client.get(
        "/inventory-items", params={"manufacturer": "dell"}, headers=headers
    )
    assert [i["id"] for i in response.json()["data"]] == [dell["id"]]

    response = client.get(
        "/inventory-items", params={"model": "latitude 5420"}, headers=headers
    )
    assert [i["id"] for i in response.json()["data"]] == [dell["id"]]


def test_filter_low_stock(
    client: TestClient, auth_headers, active_admin_user: User, cable_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    low = client.post(
        "/inventory-items",
        json=_bulk_payload(cable_category.id, stock_quantity=5, minimum_stock=10),
        headers=headers,
    ).json()["data"]
    client.post(
        "/inventory-items",
        json=_bulk_payload(cable_category.id, stock_quantity=100, minimum_stock=10),
        headers=headers,
    )

    response = client.get("/inventory-items", params={"low_stock": True}, headers=headers)
    ids = [i["id"] for i in response.json()["data"]]
    assert ids == [low["id"]]


def test_filter_warranty_expiring_days(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    soon = (date.today() + timedelta(days=10)).isoformat()
    far = (date.today() + timedelta(days=400)).isoformat()
    expiring_soon = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, warranty_expiration=soon),
        headers=headers,
    ).json()["data"]
    client.post(
        "/inventory-items",
        json=_serialized_payload(
            laptop_category.id, asset_tag="LAP-FARWARRANTY", warranty_expiration=far
        ),
        headers=headers,
    )

    response = client.get(
        "/inventory-items", params={"warranty_expiring_days": 30}, headers=headers
    )
    ids = [i["id"] for i in response.json()["data"]]
    assert ids == [expiring_soon["id"]]


# ---------------------------------------------------------------------------
# Sorting & pagination
# ---------------------------------------------------------------------------


def test_sort_by_name_ascending(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, name="Zebra Laptop", asset_tag="Z1"),
        headers=headers,
    )
    client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, name="Alpha Laptop", asset_tag="A1"),
        headers=headers,
    )

    response = client.get(
        "/inventory-items", params={"sort_by": "name", "sort_dir": "asc"}, headers=headers
    )
    names = [i["name"] for i in response.json()["data"]]
    assert names == ["Alpha Laptop", "Zebra Laptop"]


def test_sort_invalid_column_falls_back_to_created_at(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    client.post("/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers)

    response = client.get(
        "/inventory-items",
        params={"sort_by": "password_hash; DROP TABLE inventory_items;"},
        headers=headers,
    )
    assert response.status_code == 200


def test_pagination_skip_and_limit(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    for i in range(5):
        client.post(
            "/inventory-items",
            json=_serialized_payload(laptop_category.id, asset_tag=f"PAGE-{i}"),
            headers=headers,
        )

    response = client.get(
        "/inventory-items", params={"skip": 2, "limit": 2}, headers=headers
    )
    body = response.json()
    assert len(body["data"]) == 2
    assert "2 of 5" in body["msg"]


# ---------------------------------------------------------------------------
# Duplicate / cross-company asset_tag
# ---------------------------------------------------------------------------


def test_duplicate_asset_tag_in_same_company_rejected(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    client.post("/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers)
    response = client.post(
        "/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers
    )
    assert response.status_code == 409


def test_duplicate_asset_tag_across_companies_allowed(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    company_b_admin_user: User,
    laptop_category: InventoryCategory,
    company_b_inventory_category: InventoryCategory,
) -> None:
    response_a = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, asset_tag="SHARED-TAG"),
        headers=_headers(auth_headers, active_admin_user),
    )
    response_b = client.post(
        "/inventory-items",
        json=_serialized_payload(company_b_inventory_category.id, asset_tag="SHARED-TAG"),
        headers=_headers(auth_headers, company_b_admin_user),
    )
    assert response_a.status_code == 201
    assert response_b.status_code == 201


# ---------------------------------------------------------------------------
# Invalid SERIALIZED / BULK combinations
# ---------------------------------------------------------------------------


def test_serialized_without_asset_tag_rejected(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    payload = _serialized_payload(laptop_category.id)
    del payload["asset_tag"]
    response = client.post(
        "/inventory-items", json=payload, headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 400


def test_serialized_with_wrong_stock_quantity_rejected(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, stock_quantity=2),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


def test_bulk_without_stock_quantity_rejected(
    client: TestClient, auth_headers, active_admin_user: User, cable_category: InventoryCategory
) -> None:
    payload = _bulk_payload(cable_category.id)
    del payload["stock_quantity"]
    response = client.post(
        "/inventory-items", json=payload, headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 400


def test_bulk_with_invalid_status_rejected(
    client: TestClient, auth_headers, active_admin_user: User, cable_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_bulk_payload(cable_category.id, status="IN_REPAIR"),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


def test_bulk_with_holder_rejected(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    cable_category: InventoryCategory,
    active_employee_user: User,
) -> None:
    response = client.post(
        "/inventory-items",
        json=_bulk_payload(cable_category.id, current_holder_user_id=active_employee_user.id),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


def test_bulk_with_condition_rejected(
    client: TestClient, auth_headers, active_admin_user: User, cable_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_bulk_payload(cable_category.id, condition="GOOD"),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


def test_bulk_negative_stock_quantity_rejected_by_schema(
    client: TestClient, auth_headers, active_admin_user: User, cable_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_bulk_payload(cable_category.id, stock_quantity=-5),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 422


def test_negative_purchase_cost_rejected(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, purchase_cost="-1.00"),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 422


def test_warranty_before_purchase_date_rejected(
    client: TestClient, auth_headers, active_admin_user: User, laptop_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(
            laptop_category.id, purchase_date="2025-06-01", warranty_expiration="2025-01-01"
        ),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


def test_patch_bulk_item_cannot_gain_holder(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    cable_category: InventoryCategory,
    active_employee_user: User,
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-items", json=_bulk_payload(cable_category.id), headers=headers
    ).json()["data"]

    response = client.patch(
        f"/inventory-items/{created['id']}",
        json={"current_holder_user_id": active_employee_user.id},
        headers=headers,
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Invalid / inactive / cross-company references
# ---------------------------------------------------------------------------


def test_create_with_nonexistent_category_rejected(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(999999),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


def test_create_with_inactive_category_rejected(
    client: TestClient, auth_headers, active_admin_user: User, inactive_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(inactive_category.id),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


def test_patch_reassign_to_inactive_category_rejected(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    laptop_category: InventoryCategory,
    inactive_category: InventoryCategory,
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-items", json=_serialized_payload(laptop_category.id), headers=headers
    ).json()["data"]

    response = client.patch(
        f"/inventory-items/{created['id']}",
        json={"inventory_category_id": inactive_category.id},
        headers=headers,
    )
    assert response.status_code == 400


def test_create_with_foreign_company_category_rejected(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    company_b_inventory_category: InventoryCategory,
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(company_b_inventory_category.id),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


def test_create_with_foreign_company_location_rejected(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    laptop_category: InventoryCategory,
    company_b_location,
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id, current_location_id=company_b_location.id),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


def test_create_with_foreign_company_holder_rejected(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    laptop_category: InventoryCategory,
    company_b_employee_user: User,
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(
            laptop_category.id, current_holder_user_id=company_b_employee_user.id
        ),
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_company_a_cannot_list_company_b_items(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    company_b_admin_user: User,
    company_b_inventory_category: InventoryCategory,
) -> None:
    client.post(
        "/inventory-items",
        json=_serialized_payload(company_b_inventory_category.id),
        headers=_headers(auth_headers, company_b_admin_user),
    )
    response = client.get("/inventory-items", headers=_headers(auth_headers, active_admin_user))
    assert response.json()["data"] == []


def test_company_a_cannot_fetch_company_b_item_by_id(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    company_b_admin_user: User,
    company_b_inventory_category: InventoryCategory,
) -> None:
    created = client.post(
        "/inventory-items",
        json=_serialized_payload(company_b_inventory_category.id),
        headers=_headers(auth_headers, company_b_admin_user),
    ).json()["data"]

    response = client.get(
        f"/inventory-items/{created['id']}", headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 404


def test_company_a_cannot_edit_company_b_item(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    company_b_admin_user: User,
    company_b_inventory_category: InventoryCategory,
) -> None:
    created = client.post(
        "/inventory-items",
        json=_serialized_payload(company_b_inventory_category.id),
        headers=_headers(auth_headers, company_b_admin_user),
    ).json()["data"]

    response = client.patch(
        f"/inventory-items/{created['id']}",
        json={"name": "Hijacked"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_technician_can_list_and_fetch_items(
    client: TestClient, auth_headers, active_admin_user: User, active_technician_user: User, laptop_category: InventoryCategory
) -> None:
    created = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id),
        headers=_headers(auth_headers, active_admin_user),
    ).json()["data"]

    tech_headers = _headers(auth_headers, active_technician_user)
    list_response = client.get("/inventory-items", headers=tech_headers)
    assert list_response.status_code == 200

    get_response = client.get(f"/inventory-items/{created['id']}", headers=tech_headers)
    assert get_response.status_code == 200


def test_technician_cannot_create_item(
    client: TestClient, auth_headers, active_technician_user: User, laptop_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id),
        headers=_headers(auth_headers, active_technician_user),
    )
    assert response.status_code == 403


def test_technician_cannot_update_item(
    client: TestClient,
    auth_headers,
    active_admin_user: User,
    active_technician_user: User,
    laptop_category: InventoryCategory,
) -> None:
    created = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id),
        headers=_headers(auth_headers, active_admin_user),
    ).json()["data"]

    response = client.patch(
        f"/inventory-items/{created['id']}",
        json={"name": "Nope"},
        headers=_headers(auth_headers, active_technician_user),
    )
    assert response.status_code == 403


def test_employee_cannot_list_items(
    client: TestClient, auth_headers, active_employee_user: User
) -> None:
    response = client.get("/inventory-items", headers=_headers(auth_headers, active_employee_user))
    assert response.status_code == 403


def test_employee_cannot_create_item(
    client: TestClient, auth_headers, active_employee_user: User, laptop_category: InventoryCategory
) -> None:
    response = client.post(
        "/inventory-items",
        json=_serialized_payload(laptop_category.id),
        headers=_headers(auth_headers, active_employee_user),
    )
    assert response.status_code == 403
