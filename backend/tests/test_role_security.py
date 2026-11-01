"""Regression tests for two linked bugs:

1. "Technician saves as Employee": the frontend sent hardcoded role ids
   (Employee=1, Technician=2, Company Administrator=4) that did not match
   the real roles table (System Administrator=1, Employee=2, Technician=3),
   so choosing Technician stored Employee - and choosing Employee stored
   System Administrator. Role ids now come only from GET /roles, and the
   backend refuses to assign System Administrator through user management.

2. Platform access was granted by role name alone, so a tenant user whose
   role_id pointed at System Administrator could call /platform/*. Access
   now requires the role, the is_system_administrator flag, and platform
   company membership together (require_system_administrator).

Note the fixture role ids (Company Administrator=1, Employee=2,
Technician=3, System Administrator=4) deliberately differ from both the old
hardcoded frontend map and the development database - every test resolves
ids through GET /roles or the role fixtures, never by number.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.role import Role
from app.models.user import User
from tests.conftest import (
    COMPANY_A_CODE,
    COMPANY_A_ID,
    EMPLOYEE_2_PASSWORD,
    EMPLOYEE_PASSWORD,
    PLATFORM_COMPANY_CODE,
    PLATFORM_COMPANY_ID,
)

_PLATFORM_GET_PATHS = (
    "/platform/overview",
    "/platform/companies",
    f"/platform/companies/{COMPANY_A_ID}",
)
_PLATFORM_PATCH_PATHS = (
    f"/platform/companies/{COMPANY_A_ID}/activate",
    f"/platform/companies/{COMPANY_A_ID}/deactivate",
)


def _role_ids(client: TestClient, headers: dict[str, str]) -> dict[str, int]:
    resp = client.get("/roles", headers=headers)
    assert resp.status_code == 200
    return {r["name"]: r["id"] for r in resp.json()["data"]}


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/auth/login",
        json={"company_code": COMPANY_A_CODE, "username": username, "password": password},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access']}"}


def _promote_in_place(user: User, role: Role) -> None:
    """Simulate the pre-fix bug's outcome directly in storage: a tenant user
    whose role_id now points at System Administrator."""
    user.role_id = role.id
    user.role = role


# ===========================================================================
# GET /roles
# ===========================================================================


class TestRolesEndpoint:
    def test_lists_only_company_roles_with_real_ids(
        self, client, auth_headers, active_admin_user, admin_role, employee_role, technician_role
    ):
        ids = _role_ids(client, auth_headers(active_admin_user))
        assert ids == {
            "Employee": employee_role.id,
            "Technician": technician_role.id,
            "Company Administrator": admin_role.id,
        }

    def test_never_lists_system_administrator(self, client, auth_headers, active_admin_user):
        names = [r["name"] for r in client.get("/roles", headers=auth_headers(active_admin_user)).json()["data"]]
        assert "System Administrator" not in names

    @pytest.mark.parametrize("fixture", ["active_employee_user", "active_technician_user"])
    def test_non_admin_forbidden(self, request, client, auth_headers, fixture):
        user = request.getfixturevalue(fixture)
        assert client.get("/roles", headers=auth_headers(user)).status_code == 403

    def test_platform_account_forbidden(self, client, auth_headers, active_system_administrator_user):
        resp = client.get("/roles", headers=auth_headers(active_system_administrator_user))
        assert resp.status_code == 403


# ===========================================================================
# Issue 1 - Technician persistence
# ===========================================================================


class TestTechnicianRolePersistence:
    def test_employee_to_technician_to_employee(
        self, client, auth_headers, active_admin_user, active_employee_user
    ):
        admin = auth_headers(active_admin_user)
        ids = _role_ids(client, admin)
        url = f"/users/{active_employee_user.id}"

        resp = client.patch(url, json={"role_id": ids["Technician"]}, headers=admin)
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "Technician"
        # "After refresh": a fresh read returns the stored role.
        assert client.get(url, headers=admin).json()["data"]["role"] == "Technician"

        resp = client.patch(url, json={"role_id": ids["Employee"]}, headers=admin)
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "Employee"
        assert client.get(url, headers=admin).json()["data"]["role"] == "Employee"

    def test_technician_survives_logout_and_login_with_technician_permissions(
        self, client, auth_headers, active_admin_user, active_employee_user
    ):
        admin = auth_headers(active_admin_user)
        ids = _role_ids(client, admin)
        client.patch(
            f"/users/{active_employee_user.id}", json={"role_id": ids["Technician"]}, headers=admin
        )

        headers = _login(client, active_employee_user.username, EMPLOYEE_PASSWORD)
        assert client.get("/auth/me", headers=headers).json()["role"] == "Technician"
        # Technician-only access works; Company-Administrator-only does not.
        assert client.get("/inventory-items", headers=headers).status_code == 200
        assert client.get("/users", headers=headers).status_code == 403

    def test_editing_other_fields_never_changes_role(
        self, client, auth_headers, active_admin_user, active_technician_user
    ):
        resp = client.patch(
            f"/users/{active_technician_user.id}",
            json={"first_name": "Renamed"},
            headers=auth_headers(active_admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "Technician"

    def test_unknown_role_id_is_an_explicit_error(
        self, client, auth_headers, active_admin_user, active_technician_user
    ):
        resp = client.patch(
            f"/users/{active_technician_user.id}",
            json={"role_id": 9999},
            headers=auth_headers(active_admin_user),
        )
        assert resp.status_code == 400
        assert active_technician_user.role.name == "Technician"


# ===========================================================================
# Issue 2 - System Administrator cannot be obtained through user management
# ===========================================================================


class TestSystemAdministratorNotAssignable:
    def test_patch_with_system_administrator_role_id_rejected(
        self, client, auth_headers, active_admin_user, active_employee_user, system_administrator_role
    ):
        resp = client.patch(
            f"/users/{active_employee_user.id}",
            json={"role_id": system_administrator_role.id},
            headers=auth_headers(active_admin_user),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "This role cannot be assigned through user management"
        assert active_employee_user.role.name == "Employee"
        assert not active_employee_user.is_system_administrator

    def test_create_with_system_administrator_role_id_rejected(
        self, client, auth_headers, active_admin_user, system_administrator_role, user_repository
    ):
        before = len(user_repository._by_id)
        resp = client.post(
            "/users",
            json={
                "username": "sneaky",
                "first_name": "S",
                "last_name": "N",
                "email": "sneaky@itonit.test",
                "password": "SneakyPass1!",
                "role_id": system_administrator_role.id,
            },
            headers=auth_headers(active_admin_user),
        )
        assert resp.status_code == 400
        assert len(user_repository._by_id) == before

    def test_employee_cannot_change_own_role(
        self, client, auth_headers, active_employee_user, system_administrator_role
    ):
        resp = client.patch(
            f"/users/{active_employee_user.id}",
            json={"role_id": system_administrator_role.id},
            headers=auth_headers(active_employee_user),
        )
        assert resp.status_code == 403
        assert active_employee_user.role.name == "Employee"

    def test_company_admin_cannot_reach_platform_account(
        self, client, auth_headers, active_admin_user, active_system_administrator_user
    ):
        admin = auth_headers(active_admin_user)
        target = active_system_administrator_user.id
        assert client.get(f"/users/{target}", headers=admin).status_code == 404
        assert client.patch(f"/users/{target}", json={"is_active": False}, headers=admin).status_code == 404
        assert client.patch(
            f"/users/{target}/password", json={"new_password": "Takeover123!"}, headers=admin
        ).status_code == 404
        assert active_system_administrator_user.is_active is True

    def test_platform_account_cannot_be_edited_even_if_scoping_were_bypassed(
        self, db_free_user_service_for_platform_company, active_system_administrator_user
    ):
        from app.schemas.user import UserUpdate
        from app.services.user_service import UserPermissionError

        with pytest.raises(UserPermissionError):
            db_free_user_service_for_platform_company.update_user(
                active_system_administrator_user.id,
                UserUpdate(is_active=False),
                current_user=active_system_administrator_user,
            )
        assert active_system_administrator_user.is_active is True


@pytest.fixture
def db_free_user_service_for_platform_company(user_repository, role_repository, department_repository):
    """A UserService scoped to the platform company itself - unreachable
    through any route (get_current_company_id refuses platform accounts),
    used only to prove the service-level guard holds on its own."""
    from app.services.user_service import UserService
    from tests.conftest import FakeSession

    return UserService(
        db=FakeSession(),
        company_id=PLATFORM_COMPANY_ID,
        user_repository=user_repository.scoped(PLATFORM_COMPANY_ID),
        role_repository=role_repository,
        department_repository=department_repository,
    )


# ===========================================================================
# Issue 2 - platform access needs the full identity, not the role name
# ===========================================================================


class TestPlatformAccessRequiresFullIdentity:
    @pytest.mark.parametrize("path", _PLATFORM_GET_PATHS)
    def test_tenant_user_with_system_administrator_role_forbidden(
        self, client, auth_headers, active_employee_user, system_administrator_role, path
    ):
        """The user-91 scenario: role_id points at System Administrator,
        but the user is a tenant user with no flag."""
        _promote_in_place(active_employee_user, system_administrator_role)
        assert client.get(path, headers=auth_headers(active_employee_user)).status_code == 403

    @pytest.mark.parametrize("path", _PLATFORM_PATCH_PATHS)
    def test_tenant_user_with_role_cannot_mutate_companies(
        self, client, auth_headers, active_employee_user, system_administrator_role, company_a, path
    ):
        _promote_in_place(active_employee_user, system_administrator_role)
        assert client.patch(path, headers=auth_headers(active_employee_user)).status_code == 403
        assert company_a.is_active is True

    def test_tenant_user_cannot_create_companies(
        self, client, auth_headers, active_employee_user, system_administrator_role
    ):
        _promote_in_place(active_employee_user, system_administrator_role)
        resp = client.post(
            "/platform/companies",
            json={
                "company_name": "Rogue Co",
                "company_code": "ROGUE001",
                "first_name": "R",
                "last_name": "O",
                "username": "rogue",
                "email": "rogue@rogue.test",
                "password": "RoguePass1!",
            },
            headers=auth_headers(active_employee_user),
        )
        assert resp.status_code == 403

    def test_role_and_flag_without_platform_company_forbidden(
        self, client, auth_headers, active_employee_user, system_administrator_role
    ):
        _promote_in_place(active_employee_user, system_administrator_role)
        active_employee_user.is_system_administrator = True
        resp = client.get("/platform/overview", headers=auth_headers(active_employee_user))
        assert resp.status_code == 403

    def test_flag_without_role_forbidden(
        self, client, auth_headers, active_system_administrator_user, employee_role
    ):
        active_system_administrator_user.role_id = employee_role.id
        active_system_administrator_user.role = employee_role
        resp = client.get("/platform/overview", headers=auth_headers(active_system_administrator_user))
        assert resp.status_code == 403

    def test_stale_jwt_rejected_after_correction(
        self, client, active_employee_user, system_administrator_role, employee_role
    ):
        """Tokens carry only the user id, never the role: a token minted
        while the account was wrongly promoted grants nothing once the role
        is corrected - and never granted platform access in the first place."""
        stale = {"Authorization": f"Bearer {create_access_token(subject=active_employee_user.id)}"}
        _promote_in_place(active_employee_user, system_administrator_role)
        assert client.get("/platform/overview", headers=stale).status_code == 403

        _promote_in_place(active_employee_user, employee_role)
        assert client.get("/platform/overview", headers=stale).status_code == 403
        assert client.get("/auth/me", headers=stale).json()["role"] == "Employee"

    def test_tenant_user_with_role_cannot_use_platform_login(
        self, client, active_employee_user, system_administrator_role
    ):
        _promote_in_place(active_employee_user, system_administrator_role)
        for identifier in (active_employee_user.username, active_employee_user.email):
            resp = client.post(
                "/platform/login", json={"username": identifier, "password": EMPLOYEE_PASSWORD}
            )
            assert resp.status_code == 401

    def test_legitimate_system_administrator_still_has_access(
        self, client, auth_headers, active_system_administrator_user
    ):
        headers = auth_headers(active_system_administrator_user)
        for path in _PLATFORM_GET_PATHS:
            assert client.get(path, headers=headers).status_code == 200
        resp = client.post(
            "/platform/login",
            json={"username": active_system_administrator_user.username, "password": "PlatformAdminPass1!"},
        )
        assert resp.status_code == 200


# ===========================================================================
# Issue 2 - the platform company is not a customer tenant
# ===========================================================================


class TestPlatformCompanySeparation:
    def test_platform_account_cannot_use_tenant_routes(
        self, client, auth_headers, active_system_administrator_user
    ):
        headers = auth_headers(active_system_administrator_user)
        for path in ("/users", "/departments", "/priorities", "/analytics/tickets"):
            assert client.get(path, headers=headers).status_code == 403

    def test_company_code_login_refuses_platform_company(
        self, client, active_system_administrator_user
    ):
        resp = client.post(
            "/auth/login",
            json={
                "company_code": PLATFORM_COMPANY_CODE,
                "username": active_system_administrator_user.username,
                "password": "PlatformAdminPass1!",
            },
        )
        assert resp.status_code == 401

    def test_resolve_company_hides_platform_company(self, client):
        resp = client.post("/auth/resolve-company", json={"company_code": PLATFORM_COMPANY_CODE})
        assert resp.status_code == 404

    def test_platform_company_not_listed_or_counted(
        self, client, auth_headers, active_system_administrator_user
    ):
        headers = auth_headers(active_system_administrator_user)
        listed = client.get("/platform/companies", headers=headers).json()
        assert PLATFORM_COMPANY_ID not in [c["id"] for c in listed["data"]]
        overview = client.get("/platform/overview", headers=headers).json()["data"]
        assert overview["total_companies"] == listed["total"]

    @pytest.mark.parametrize(
        "method,suffix", [("get", ""), ("patch", "/activate"), ("patch", "/deactivate")]
    )
    def test_platform_company_not_manageable_as_customer(
        self, client, auth_headers, active_system_administrator_user, platform_company, method, suffix
    ):
        resp = getattr(client, method)(
            f"/platform/companies/{PLATFORM_COMPANY_ID}{suffix}",
            headers=auth_headers(active_system_administrator_user),
        )
        assert resp.status_code == 404
        assert platform_company.is_active is True

    def test_reserved_code_cannot_be_provisioned(
        self, client, auth_headers, active_system_administrator_user
    ):
        resp = client.post(
            "/platform/companies",
            json={
                "company_name": "Impostor",
                "company_code": PLATFORM_COMPANY_CODE.lower(),
                "first_name": "I",
                "last_name": "M",
                "username": "impostor",
                "email": "impostor@impostor.test",
                "password": "ImpostorPass1!",
            },
            headers=auth_headers(active_system_administrator_user),
        )
        assert resp.status_code == 409


# ===========================================================================
# Issue 1 - the complete Technician workflow, end to end
# ===========================================================================


class TestTechnicianWorkflowEndToEnd:
    """One user goes Employee -> Technician -> Employee through the real
    API, using ids from GET /roles only, and gets exactly the permission
    model routes/tickets.py defines at each step: _VIEW_ROLES,
    _STATUS_ROLES, _INVENTORY_ROLES include Technician; _CREATE_ROLES,
    _ASSIGN_ROLES, _DELETE_ROLES and every admin route do not."""

    def test_full_promotion_work_and_demotion_cycle(
        self, client, auth_headers, active_admin_user, active_employee_user_2, employee_ticket
    ):
        admin = auth_headers(active_admin_user)
        ids = _role_ids(client, admin)
        user_url = f"/users/{active_employee_user_2.id}"
        ticket_id = employee_ticket.id

        # Before promotion: ticket assignment refuses a non-Technician.
        resp = client.patch(
            f"/tickets/{ticket_id}/assign",
            json={"technician_id": active_employee_user_2.id},
            headers=admin,
        )
        assert resp.status_code == 400

        # Employee -> Technician, persisted with the exact id GET /roles gave.
        resp = client.patch(user_url, json={"role_id": ids["Technician"]}, headers=admin)
        assert resp.status_code == 200
        assert active_employee_user_2.role_id == ids["Technician"]
        listed = client.get("/users", params={"role_id": ids["Technician"]}, headers=admin)
        assert active_employee_user_2.id in [u["id"] for u in listed.json()["data"]]

        # Log out / log back in: a fresh token still resolves Technician.
        tech = _login(client, active_employee_user_2.username, EMPLOYEE_2_PASSWORD)
        assert client.get("/auth/me", headers=tech).json()["role"] == "Technician"

        # Now assignable, and the ticket shows up in the Technician's list.
        resp = client.patch(
            f"/tickets/{ticket_id}/assign",
            json={"technician_id": active_employee_user_2.id},
            headers=admin,
        )
        assert resp.status_code == 200
        assigned = client.get("/all-tickets", headers=tech).json()["data"]
        assert [t["id"] for t in assigned] == [ticket_id]

        # Technician actions on an assigned ticket.
        assert client.get(f"/tickets/{ticket_id}", headers=tech).status_code == 200
        resp = client.patch(f"/tickets/{ticket_id}/status", json={"status": "IN_PROGRESS"}, headers=tech)
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_PROGRESS"
        resp = client.post(f"/tickets/{ticket_id}/comments", json={"content": "On it"}, headers=tech)
        assert resp.status_code == 201
        assert client.get(f"/tickets/{ticket_id}/inventory", headers=tech).status_code == 200
        assert client.get("/inventory-items", headers=tech).status_code == 200

        # Not Company Administrator, not System Administrator.
        assert client.delete(f"/tickets/{ticket_id}", headers=tech).status_code == 403
        assert client.patch(
            f"/tickets/{ticket_id}/assign", json={"technician_id": active_employee_user_2.id}, headers=tech
        ).status_code == 403
        for path in ("/users", "/roles", "/platform/overview", "/platform/companies"):
            assert client.get(path, headers=tech).status_code == 403
        assert client.patch(
            user_url, json={"role_id": ids["Company Administrator"]}, headers=tech
        ).status_code == 403
        assert active_employee_user_2.role.name == "Technician"

        # Technician -> Employee: Technician-only actions stop immediately,
        # even with the token issued while they were a Technician.
        resp = client.patch(user_url, json={"role_id": ids["Employee"]}, headers=admin)
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "Employee"
        assert client.get("/auth/me", headers=tech).json()["role"] == "Employee"
        assert client.patch(
            f"/tickets/{ticket_id}/status", json={"status": "RESOLVED"}, headers=tech
        ).status_code == 403
        assert client.get("/inventory-items", headers=tech).status_code == 403

    def test_technician_cannot_touch_unassigned_ticket(
        self, client, auth_headers, active_admin_user, active_employee_user_2, employee_ticket
    ):
        admin = auth_headers(active_admin_user)
        ids = _role_ids(client, admin)
        client.patch(
            f"/users/{active_employee_user_2.id}", json={"role_id": ids["Technician"]}, headers=admin
        )
        tech = auth_headers(active_employee_user_2)
        assert client.get("/all-tickets", headers=tech).json()["data"] == []
        resp = client.patch(
            f"/tickets/{employee_ticket.id}/status", json={"status": "IN_PROGRESS"}, headers=tech
        )
        assert resp.status_code in (403, 404)

    @pytest.mark.parametrize("target", ["Employee", "Technician", "Company Administrator"])
    def test_every_company_role_round_trips(
        self, client, auth_headers, active_admin_user, active_employee_user_2, target
    ):
        admin = auth_headers(active_admin_user)
        ids = _role_ids(client, admin)
        resp = client.patch(
            f"/users/{active_employee_user_2.id}", json={"role_id": ids[target]}, headers=admin
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == target
        assert active_employee_user_2.role_id == ids[target]
        assert not active_employee_user_2.is_system_administrator

    def test_create_user_directly_as_technician(self, client, auth_headers, active_admin_user):
        admin = auth_headers(active_admin_user)
        ids = _role_ids(client, admin)
        resp = client.post(
            "/users",
            json={
                "username": "newtech",
                "first_name": "New",
                "last_name": "Tech",
                "email": "newtech@itonit.test",
                "password": "NewTechPass1!",
                "role_id": ids["Technician"],
            },
            headers=admin,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["role"] == "Technician"
        # Re-read rather than log in: the fake repository's create() doesn't
        # populate the .company relationship a real session would lazy-load.
        new_id = resp.json()["data"]["id"]
        assert client.get(f"/users/{new_id}", headers=admin).json()["data"]["role"] == "Technician"

    def test_no_role_id_in_any_range_grants_platform_access(
        self, client, auth_headers, active_admin_user, active_employee_user_2, role_repository
    ):
        """Sweep every existing role id plus out-of-range ones: none may
        leave the user with platform access or the System Administrator role."""
        admin = auth_headers(active_admin_user)
        for role_id in [*role_repository._by_id, 0, -1, 9999]:
            client.patch(f"/users/{active_employee_user_2.id}", json={"role_id": role_id}, headers=admin)
            assert active_employee_user_2.role.name != "System Administrator"
            assert not active_employee_user_2.is_system_administrator
            resp = client.get("/platform/overview", headers=auth_headers(active_employee_user_2))
            assert resp.status_code == 403
