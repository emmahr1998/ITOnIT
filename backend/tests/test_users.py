from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.department import Department
from app.models.role import Role
from app.models.user import User

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_user_succeeds_for_admin(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_role: Role,
    it_department: Department,
) -> None:
    response = client.post(
        "/users",
        json={
            "username": "newhire",
            "first_name": "New",
            "last_name": "Hire",
            "email": "newhire@itonit.test",
            "department_id": it_department.id,
            "phone_number": "555-0100",
            "password": "SuperSecret1!",
            "role_id": employee_role.id,
            "theme": "dark",
        },
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["username"] == "newhire"
    assert body["email"] == "newhire@itonit.test"
    assert body["role"] == "Employee"
    assert body["department"]["title"] == "IT"
    assert "password" not in body
    assert "password_hash" not in body


def test_create_user_succeeds_for_a_second_company_administrator(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_role: Role,
) -> None:
    """Company Administrator is not a singular role - a second, distinct
    Company Administrator (active_manager_user, formerly a Manager before
    that role was merged in) has identical permissions to the first,
    including user creation, which used to be Administrator-only."""
    response = client.post(
        "/users",
        json={
            "username": "newhire2",
            "first_name": "New",
            "last_name": "Hire",
            "email": "newhire2@itonit.test",
            "password": "SuperSecret1!",
            "role_id": employee_role.id,
        },
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 201
    assert response.json()["data"]["username"] == "newhire2"


def test_create_user_forbidden_for_non_admin(
    client: TestClient,
    active_technician_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_role: Role,
) -> None:
    response = client.post(
        "/users",
        json={
            "username": "newhire",
            "first_name": "New",
            "last_name": "Hire",
            "email": "newhire@itonit.test",
            "password": "SuperSecret1!",
            "role_id": employee_role.id,
        },
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 403


def test_create_user_duplicate_username_returns_409(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    active_employee_user: User,
    employee_role: Role,
) -> None:
    response = client.post(
        "/users",
        json={
            "username": active_employee_user.username,
            "first_name": "New",
            "last_name": "Hire",
            "email": "different@itonit.test",
            "password": "SuperSecret1!",
            "role_id": employee_role.id,
        },
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_create_user_duplicate_email_returns_409(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    active_employee_user: User,
    employee_role: Role,
) -> None:
    response = client.post(
        "/users",
        json={
            "username": "different",
            "first_name": "New",
            "last_name": "Hire",
            "email": active_employee_user.email,
            "password": "SuperSecret1!",
            "role_id": employee_role.id,
        },
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_create_user_unknown_role_returns_400(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.post(
        "/users",
        json={
            "username": "newhire",
            "first_name": "New",
            "last_name": "Hire",
            "email": "newhire@itonit.test",
            "password": "SuperSecret1!",
            "role_id": 999999,
        },
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 400


def test_create_user_unknown_department_returns_400(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    employee_role: Role,
) -> None:
    response = client.post(
        "/users",
        json={
            "username": "newhire",
            "first_name": "New",
            "last_name": "Hire",
            "email": "newhire@itonit.test",
            "department_id": 999999,
            "password": "SuperSecret1!",
            "role_id": employee_role.id,
        },
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 400


def test_create_user_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/users",
        json={
            "username": "newhire",
            "first_name": "New",
            "last_name": "Hire",
            "email": "newhire@itonit.test",
            "password": "SuperSecret1!",
            "role_id": 1,
        },
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_users_succeeds_for_company_administrator(
    client: TestClient,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/users", headers=auth_headers(active_manager_user))
    assert response.status_code == 200
    usernames = {u["username"] for u in response.json()["data"]}
    assert "employee" in usernames


def test_list_users_forbidden_for_employee(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/users", headers=auth_headers(active_employee_user))
    assert response.status_code == 403


def test_list_users_filters_by_role(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    technician_role: Role,
) -> None:
    response = client.get(
        "/users",
        params={"role_id": technician_role.id},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    roles = {u["role"] for u in response.json()["data"]}
    assert roles == {"Technician"}


def test_list_users_search_matches_username(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get(
        "/users", params={"search": "employee2"}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 200
    usernames = {u["username"] for u in response.json()["data"]}
    assert usernames == {"employee2"}


# ---------------------------------------------------------------------------
# Get by id
# ---------------------------------------------------------------------------


def test_get_user_succeeds_for_company_administrator_viewing_someone_else(
    client: TestClient,
    active_manager_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get(
        f"/users/{active_employee_user.id}", headers=auth_headers(active_manager_user)
    )
    assert response.status_code == 200
    assert response.json()["data"]["username"] == active_employee_user.username


def test_get_user_succeeds_for_self(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get(
        f"/users/{active_employee_user.id}", headers=auth_headers(active_employee_user)
    )
    assert response.status_code == 200


def test_get_user_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user: User,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get(
        f"/users/{active_employee_user.id}", headers=auth_headers(active_employee_user_2)
    )
    assert response.status_code == 403


def test_get_user_unknown_id_returns_404(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.get("/users/999999", headers=auth_headers(active_admin_user))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_user_admin_can_change_administrative_fields(
    client: TestClient,
    active_admin_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    technician_role: Role,
) -> None:
    response = client.patch(
        f"/users/{active_employee_user.id}",
        json={"role_id": technician_role.id, "is_active": False},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["role"] == "Technician"
    assert body["is_active"] is False


def test_update_user_succeeds_for_a_second_company_administrator(
    client: TestClient,
    active_manager_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    technician_role: Role,
) -> None:
    """Company Administrator is not a singular role - a second, distinct
    Company Administrator (active_manager_user, formerly a Manager before
    that role was merged in) has identical permissions to the first,
    including fully editing another user's administrative fields, which
    used to be Administrator-only."""
    response = client.patch(
        f"/users/{active_employee_user.id}",
        json={"role_id": technician_role.id, "is_active": False},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["role"] == "Technician"
    assert body["is_active"] is False


def test_update_user_self_can_change_safe_fields(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        f"/users/{active_employee_user.id}",
        json={"first_name": "Evelyn", "theme": "dark"},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["first_name"] == "Evelyn"
    assert body["theme"] == "dark"


def test_update_user_self_forbidden_from_administrative_field(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    technician_role: Role,
) -> None:
    response = client.patch(
        f"/users/{active_employee_user.id}",
        json={"role_id": technician_role.id},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 403


def test_update_user_forbidden_for_other_employee(
    client: TestClient,
    active_employee_user: User,
    active_employee_user_2: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        f"/users/{active_employee_user.id}",
        json={"first_name": "Hijacked"},
        headers=auth_headers(active_employee_user_2),
    )
    assert response.status_code == 403


def test_update_user_duplicate_username_returns_409(
    client: TestClient,
    active_admin_user: User,
    active_employee_user: User,
    active_manager_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        f"/users/{active_employee_user.id}",
        json={"username": active_manager_user.username},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 409


def test_update_user_unknown_id_returns_404(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        "/users/999999", json={"first_name": "Nobody"}, headers=auth_headers(active_admin_user)
    )
    assert response.status_code == 404


def test_update_user_password_not_accepted(
    client: TestClient,
    active_admin_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    """PATCH /users/{id} never accepts a password - extra fields are ignored
    by default, so this must succeed while leaving the password untouched."""
    response = client.patch(
        f"/users/{active_employee_user.id}",
        json={"first_name": "Eve", "password": "ShouldNotWork1!"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200
    assert "password" not in response.json()["data"]
