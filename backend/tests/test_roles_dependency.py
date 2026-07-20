import pytest
from fastapi import HTTPException

from app.dependencies.auth import get_current_active_user, require_roles
from app.models.user import User


def test_get_current_active_user_allows_active_user(active_admin_user: User) -> None:
    assert get_current_active_user(current_user=active_admin_user) is active_admin_user


def test_get_current_active_user_rejects_inactive_user(inactive_user: User) -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_active_user(current_user=inactive_user)
    assert exc_info.value.status_code == 401


def test_require_roles_allows_permitted_role(active_admin_user: User) -> None:
    dependency = require_roles("Administrator")
    assert dependency(current_user=active_admin_user) is active_admin_user


def test_require_roles_rejects_forbidden_role(active_admin_user: User) -> None:
    dependency = require_roles("Technician")
    with pytest.raises(HTTPException) as exc_info:
        dependency(current_user=active_admin_user)
    assert exc_info.value.status_code == 403
