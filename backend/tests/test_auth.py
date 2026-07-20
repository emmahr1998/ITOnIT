from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.user import User


def test_login_succeeds_with_correct_credentials(
    client: TestClient, active_admin_user: User, admin_password: str
) -> None:
    response = client.post(
        "/auth/login",
        json={"email": active_admin_user.email, "password": admin_password},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_rejects_wrong_password(client: TestClient, active_admin_user: User) -> None:
    response = client.post(
        "/auth/login",
        json={"email": active_admin_user.email, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_rejects_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "nobody@itonit.test", "password": "whatever"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_rejects_inactive_user(
    client: TestClient, inactive_user: User, inactive_password: str
) -> None:
    response = client.post(
        "/auth/login",
        json={"email": inactive_user.email, "password": inactive_password},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


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
