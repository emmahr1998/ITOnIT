from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.user import User


def test_change_own_password_succeeds(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        "/users/me/password",
        json={"current_password": "EmployeePass1!", "new_password": "BrandNewPass1!"},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 200

    # Old password no longer works.
    old_login = client.post(
        "/auth/login",
        json={"username": active_employee_user.username, "password": "EmployeePass1!"},
    )
    assert old_login.status_code == 401

    # New password works.
    new_login = client.post(
        "/auth/login",
        json={"username": active_employee_user.username, "password": "BrandNewPass1!"},
    )
    assert new_login.status_code == 200


def test_change_own_password_rejects_wrong_current_password(
    client: TestClient,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        "/users/me/password",
        json={"current_password": "WrongPassword1!", "new_password": "BrandNewPass1!"},
        headers=auth_headers(active_employee_user),
    )
    assert response.status_code == 400

    # Original password still works.
    login = client.post(
        "/auth/login",
        json={"username": active_employee_user.username, "password": "EmployeePass1!"},
    )
    assert login.status_code == 200


def test_change_own_password_requires_authentication(client: TestClient) -> None:
    response = client.patch(
        "/users/me/password",
        json={"current_password": "whatever", "new_password": "BrandNewPass1!"},
    )
    assert response.status_code == 401


def test_admin_set_password_succeeds_without_current_password(
    client: TestClient,
    active_admin_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        f"/users/{active_employee_user.id}/password",
        json={"new_password": "AdminSetThis1!"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 200

    new_login = client.post(
        "/auth/login",
        json={"username": active_employee_user.username, "password": "AdminSetThis1!"},
    )
    assert new_login.status_code == 200


def test_admin_set_password_succeeds_for_a_second_company_administrator(
    client: TestClient,
    active_manager_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    """Company Administrator is not a singular role - a second, distinct
    Company Administrator (active_manager_user, formerly a Manager before
    that role was merged in) has identical permissions to the first,
    including setting another user's password, which used to be
    Administrator-only."""
    response = client.patch(
        f"/users/{active_employee_user.id}/password",
        json={"new_password": "SetByAdmin2_1!"},
        headers=auth_headers(active_manager_user),
    )
    assert response.status_code == 200


def test_admin_set_password_forbidden_for_non_admin(
    client: TestClient,
    active_technician_user: User,
    active_employee_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        f"/users/{active_employee_user.id}/password",
        json={"new_password": "ShouldNotWork1!"},
        headers=auth_headers(active_technician_user),
    )
    assert response.status_code == 403


def test_admin_set_password_unknown_user_returns_404(
    client: TestClient,
    active_admin_user: User,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    response = client.patch(
        "/users/999999/password",
        json={"new_password": "ShouldNotWork1!"},
        headers=auth_headers(active_admin_user),
    )
    assert response.status_code == 404


def test_admin_set_password_requires_authentication(client: TestClient) -> None:
    response = client.patch(
        "/users/1/password", json={"new_password": "ShouldNotWork1!"}
    )
    assert response.status_code == 401
