from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_refresh_token, verify_password
from app.models.user import User


def test_register_creates_active_employee_and_signs_in(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": "newperson",
            "first_name": "New",
            "last_name": "Person",
            "email": "newperson@example.com",
            "password": "SuperSecret1!",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access"], str) and body["access"]
    assert isinstance(body["refresh"], str) and body["refresh"]

    # The new account can immediately reach an authenticated endpoint, and
    # is an Employee regardless of anything the request tried to imply.
    me_response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {body['access']}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "Employee"


def test_register_hashes_the_password(client: TestClient, user_repository) -> None:
    client.post(
        "/auth/register",
        json={
            "username": "hashcheck",
            "first_name": "Hash",
            "last_name": "Check",
            "email": "hashcheck@example.com",
            "password": "SuperSecret1!",
        },
    )
    created = user_repository.get_by_username("hashcheck")
    assert created is not None
    assert created.password_hash != "SuperSecret1!"
    assert verify_password("SuperSecret1!", created.password_hash)


def test_register_ignores_client_supplied_role(client: TestClient) -> None:
    """RegisterRequest has no role_id field at all, so even trying to send
    one has no effect - the account is still created as an Employee."""
    response = client.post(
        "/auth/register",
        json={
            "username": "wannabeadmin",
            "first_name": "Wannabe",
            "last_name": "Admin",
            "email": "wannabeadmin@example.com",
            "password": "SuperSecret1!",
            "role_id": 1,
        },
    )
    assert response.status_code == 201
    access = response.json()["access"]
    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me_response.json()["role"] == "Employee"


def test_register_rejects_duplicate_username(
    client: TestClient, active_admin_user: User
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": active_admin_user.username,
            "first_name": "Dup",
            "last_name": "User",
            "email": "someoneelse@example.com",
            "password": "SuperSecret1!",
        },
    )
    assert response.status_code == 409
    assert "username" in response.json()["detail"]


def test_register_rejects_duplicate_email(
    client: TestClient, active_admin_user: User
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": "someoneelse",
            "first_name": "Dup",
            "last_name": "User",
            "email": active_admin_user.email,
            "password": "SuperSecret1!",
        },
    )
    assert response.status_code == 409
    assert "email" in response.json()["detail"]


def test_register_rejects_short_password(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": "shortpw",
            "first_name": "Short",
            "last_name": "Pw",
            "email": "shortpw@example.com",
            "password": "short",
        },
    )
    assert response.status_code == 422


def test_login_succeeds_with_correct_credentials(
    client: TestClient, active_admin_user: User, admin_password: str
) -> None:
    response = client.post(
        "/auth/login",
        json={"username": active_admin_user.username, "password": admin_password},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access"], str) and body["access"]
    assert isinstance(body["refresh"], str) and body["refresh"]
    assert body["access"] != body["refresh"]


def test_login_succeeds_with_email_for_backward_compatibility(
    client: TestClient, active_admin_user: User, admin_password: str
) -> None:
    """username is the documented login field, but the lookup also matches
    email in the same query, so existing email-based logins keep working."""
    response = client.post(
        "/auth/login",
        json={"username": active_admin_user.email, "password": admin_password},
    )
    assert response.status_code == 200
    assert response.json()["access"]


def test_login_rejects_wrong_password(client: TestClient, active_admin_user: User) -> None:
    response = client.post(
        "/auth/login",
        json={"username": active_admin_user.username, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_rejects_unknown_username(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": "nobody", "password": "whatever"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_rejects_inactive_user(
    client: TestClient, inactive_user: User, inactive_password: str
) -> None:
    response = client.post(
        "/auth/login",
        json={"username": inactive_user.username, "password": inactive_password},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_refresh_succeeds_with_valid_refresh_token(
    client: TestClient, active_admin_user: User, admin_password: str
) -> None:
    login_response = client.post(
        "/auth/login",
        json={"username": active_admin_user.username, "password": admin_password},
    )
    refresh_token = login_response.json()["refresh"]

    response = client.post("/auth/refresh", json={"refresh": refresh_token})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access"], str) and body["access"]

    # The new access token actually works.
    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access']}"})
    assert me_response.status_code == 200


def test_refresh_rejects_an_access_token(client: TestClient, active_admin_user: User) -> None:
    """An access token must not work as a refresh token."""
    access_token = create_access_token(subject=active_admin_user.id)
    response = client.post("/auth/refresh", json={"refresh": access_token})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"


def test_refresh_token_cannot_be_used_as_an_access_token(
    client: TestClient, active_admin_user: User
) -> None:
    """A refresh token must not work as an access token."""
    refresh_token = create_refresh_token(subject=active_admin_user.id)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 401


def test_refresh_rejects_garbage_token(client: TestClient) -> None:
    response = client.post("/auth/refresh", json={"refresh": "not-a-real-token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"


def test_refresh_rejects_inactive_user(
    client: TestClient, inactive_user: User
) -> None:
    refresh_token = create_refresh_token(subject=inactive_user.id)
    response = client.post("/auth/refresh", json={"refresh": refresh_token})
    assert response.status_code == 401


def test_me_succeeds_with_valid_token(client: TestClient, active_admin_user: User) -> None:
    token = create_access_token(subject=active_admin_user.id)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == active_admin_user.email
    assert body["role"] == "Administrator"
    assert "password_hash" not in body
    assert "password" not in body


def test_me_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer garbage-token"})
    assert response.status_code == 401
