"""Tests for InventoryCategory CRUD (Phase 10.2) - GET/POST/PATCH
/inventory-categories. No DELETE endpoint exists; deactivation is via
PATCH is_active=False (see app/services/inventory_category_service.py).
"""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.user import User


def _headers(auth_headers: Callable[[User], dict[str, str]], user: User) -> dict[str, str]:
    return auth_headers(user)


# ---------------------------------------------------------------------------
# List / create / get / update - happy paths
# ---------------------------------------------------------------------------


def test_list_inventory_categories_starts_empty(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    response = client.get("/inventory-categories", headers=_headers(auth_headers, active_admin_user))
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_create_inventory_category_succeeds(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    response = client.post(
        "/inventory-categories",
        json={"name": "Laptop"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["name"] == "Laptop"
    assert body["is_active"] is True
    assert "id" in body and "created_at" in body


def test_create_inventory_category_trims_whitespace(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    response = client.post(
        "/inventory-categories",
        json={"name": "  Laptop  "},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 201
    assert response.json()["data"]["name"] == "Laptop"


def test_create_inventory_category_rejects_blank_name(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    response = client.post(
        "/inventory-categories",
        json={"name": "   "},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 422


def test_create_inventory_category_duplicate_name_returns_409(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    client.post("/inventory-categories", json={"name": "Laptop"}, headers=headers)
    response = client.post("/inventory-categories", json={"name": "Laptop"}, headers=headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_create_inventory_category_duplicate_name_case_insensitive(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    client.post("/inventory-categories", json={"name": "Laptop"}, headers=headers)
    response = client.post("/inventory-categories", json={"name": "laptop"}, headers=headers)
    assert response.status_code == 409


def test_get_inventory_category_by_id(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post("/inventory-categories", json={"name": "Monitor"}, headers=headers)
    category_id = created.json()["data"]["id"]

    response = client.get(f"/inventory-categories/{category_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Monitor"


def test_get_inventory_category_not_found(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    response = client.get(
        "/inventory-categories/999999", headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 404


def test_update_inventory_category_rename(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post("/inventory-categories", json={"name": "Keyboad"}, headers=headers)
    category_id = created.json()["data"]["id"]

    response = client.patch(
        f"/inventory-categories/{category_id}", json={"name": "Keyboard"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Keyboard"


def test_update_inventory_category_deactivate(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    created = client.post("/inventory-categories", json={"name": "Old Dock"}, headers=headers)
    category_id = created.json()["data"]["id"]

    response = client.patch(
        f"/inventory-categories/{category_id}", json={"is_active": False}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False

    # Inactive categories remain queryable - no DELETE endpoint exists.
    fetch = client.get(f"/inventory-categories/{category_id}", headers=headers)
    assert fetch.status_code == 200
    assert fetch.json()["data"]["is_active"] is False


def test_update_inventory_category_rename_conflict(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    headers = _headers(auth_headers, active_admin_user)
    client.post("/inventory-categories", json={"name": "Phone"}, headers=headers)
    other = client.post("/inventory-categories", json={"name": "Tablet"}, headers=headers)
    other_id = other.json()["data"]["id"]

    response = client.patch(
        f"/inventory-categories/{other_id}", json={"name": "Phone"}, headers=headers
    )
    assert response.status_code == 409


def test_update_inventory_category_not_found(
    client: TestClient, auth_headers, active_admin_user: User
) -> None:
    response = client.patch(
        "/inventory-categories/999999",
        json={"name": "Whatever"},
        headers=_headers(auth_headers, active_admin_user),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Permissions - Employee has no inventory access at all; Technician is
# read-only; Company Administrator has full CRUD.
# ---------------------------------------------------------------------------


def test_employee_cannot_list_inventory_categories(
    client: TestClient, auth_headers, active_employee_user: User
) -> None:
    response = client.get(
        "/inventory-categories", headers=_headers(auth_headers, active_employee_user)
    )
    assert response.status_code == 403


def test_employee_cannot_create_inventory_category(
    client: TestClient, auth_headers, active_employee_user: User
) -> None:
    response = client.post(
        "/inventory-categories",
        json={"name": "Anything"},
        headers=_headers(auth_headers, active_employee_user),
    )
    assert response.status_code == 403


def test_technician_can_list_inventory_categories(
    client: TestClient, auth_headers, active_technician_user: User
) -> None:
    response = client.get(
        "/inventory-categories", headers=_headers(auth_headers, active_technician_user)
    )
    assert response.status_code == 200


def test_technician_cannot_create_inventory_category(
    client: TestClient, auth_headers, active_technician_user: User
) -> None:
    response = client.post(
        "/inventory-categories",
        json={"name": "Anything"},
        headers=_headers(auth_headers, active_technician_user),
    )
    assert response.status_code == 403


def test_technician_cannot_update_inventory_category(
    client: TestClient, auth_headers, active_admin_user: User, active_technician_user: User
) -> None:
    admin_headers = _headers(auth_headers, active_admin_user)
    created = client.post(
        "/inventory-categories", json={"name": "Router"}, headers=admin_headers
    )
    category_id = created.json()["data"]["id"]

    response = client.patch(
        f"/inventory-categories/{category_id}",
        json={"name": "Switch"},
        headers=_headers(auth_headers, active_technician_user),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_company_a_cannot_see_company_b_inventory_categories(
    client: TestClient, auth_headers, active_admin_user: User, company_b_admin_user: User
) -> None:
    client.post(
        "/inventory-categories",
        json={"name": "Company B Only"},
        headers=_headers(auth_headers, company_b_admin_user),
    )
    response = client.get(
        "/inventory-categories", headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_company_a_cannot_fetch_company_b_inventory_category_by_id(
    client: TestClient, auth_headers, active_admin_user: User, company_b_admin_user: User
) -> None:
    created = client.post(
        "/inventory-categories",
        json={"name": "Company B Category"},
        headers=_headers(auth_headers, company_b_admin_user),
    )
    category_id = created.json()["data"]["id"]

    response = client.get(
        f"/inventory-categories/{category_id}", headers=_headers(auth_headers, active_admin_user)
    )
    assert response.status_code == 404


def test_duplicate_name_allowed_across_companies(
    client: TestClient, auth_headers, active_admin_user: User, company_b_admin_user: User
) -> None:
    response_a = client.post(
        "/inventory-categories",
        json={"name": "Shared Name"},
        headers=_headers(auth_headers, active_admin_user),
    )
    response_b = client.post(
        "/inventory-categories",
        json={"name": "Shared Name"},
        headers=_headers(auth_headers, company_b_admin_user),
    )
    assert response_a.status_code == 201
    assert response_b.status_code == 201
