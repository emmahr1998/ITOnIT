from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_refresh_token
from app.models.user import User


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
