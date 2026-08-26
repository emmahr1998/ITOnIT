from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, hash_password
from app.dependencies.attachment import get_attachment_service
from app.dependencies.auth import get_auth_service, get_current_company_id, get_user_repository
from app.dependencies.category import get_category_service
from app.dependencies.comment import get_comment_service
from app.dependencies.company import get_company_service
from app.dependencies.department import get_department_service
from app.dependencies.history import get_history_service
from app.dependencies.inventory_category import get_inventory_category_service
from app.dependencies.inventory_item import get_inventory_item_service
from app.dependencies.inventory_transaction import get_inventory_transaction_service
from app.dependencies.location import get_location_service
from app.dependencies.priority import get_priority_service
from app.dependencies.ticket import get_ticket_service
from app.dependencies.ticket_inventory import get_ticket_inventory_service
from app.dependencies.user import get_user_service
from app.main import app
from app.models.attachment import Attachment
from app.models.category import Category
from app.models.comment import Comment
from app.models.company import Company
from app.models.department import Department
from app.models.enums import (
    InventoryCondition,
    InventoryStatus,
    InventoryTrackingType,
    TicketStatus,
)
from app.models.inventory_category import InventoryCategory
from app.models.inventory_item import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.location import Location
from app.models.priority import Priority
from app.models.role import Role
from app.models.ticket import Ticket
from app.models.ticket_history import TicketHistory
from app.models.ticket_inventory_usage import TicketInventoryUsage
from app.models.user import User
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.category_service import CategoryService
from app.services.comment_service import CommentService
from app.services.company_service import CompanyService
from app.services.department_service import DepartmentService
from app.services.history_service import HistoryService
from app.services.inventory_category_service import InventoryCategoryService
from app.services.inventory_item_service import InventoryItemService
from app.services.inventory_transaction_service import InventoryTransactionService
from app.services.location_service import LocationService
from app.services.priority_service import PriorityService
from app.services.ticket_inventory_service import TicketInventoryService
from app.services.ticket_service import TicketService
from app.services.user_service import UserService

ADMIN_PASSWORD = "CorrectHorseBattery1!"
INACTIVE_PASSWORD = "SomePassword1!"
EMPLOYEE_PASSWORD = "EmployeePass1!"
TECHNICIAN_PASSWORD = "TechnicianPass1!"
MANAGER_PASSWORD = "ManagerPass1!"
EMPLOYEE_2_PASSWORD = "EmployeeTwoPass1!"
TECHNICIAN_2_PASSWORD = "TechnicianTwoPass1!"

# The two tenants every cross-company isolation test plays "Company A" and
# "Company B" against. All the pre-existing (Company A) fixtures below were
# already implicitly single-tenant; COMPANY_A_ID is what makes that
# explicit now that every tenant-owned model has a company_id column.
COMPANY_A_ID = 1
COMPANY_B_ID = 2
COMPANY_B_ADMIN_PASSWORD = "CompanyBAdminPass1!"
COMPANY_B_TECHNICIAN_PASSWORD = "CompanyBTechPass1!"
COMPANY_B_EMPLOYEE_PASSWORD = "CompanyBEmployeePass1!"

# Company codes for the company-code-first login flow (Milestone 4).
COMPANY_A_CODE = "COMPANYA1"
COMPANY_B_CODE = "COMPANYB1"
SUSPENDED_COMPANY_ID = 3
SUSPENDED_COMPANY_CODE = "SUSPENDED1"


class FakeUserRepository:
    """In-memory stand-in for UserRepository.

    Auth/user-management tests must not touch the real SQL-Server-only
    database, and the production models aren't SQLite-compatible enough to
    fake with an in-memory engine. Instead, AuthService/UserService and the
    auth dependencies accept a repository object structurally (same method
    names/signatures as UserRepository), so this plain Python class -
    backed by a dict of plain (unsaved) User/Role ORM instances -
    substitutes for it without ever creating an engine or session.
    """

    def __init__(self, users: list[User], company_id: int | None = None) -> None:
        self._by_id = {user.id: user for user in users}
        self._id_seq = [max(self._by_id, default=0) + 1]
        # None = unscoped, matching real UserRepository's default - used
        # for get_current_user, which must resolve a user before any
        # company is known. The base instance built by the user_repository
        # fixture stays unscoped forever; per-request company scoping for
        # user-management calls is done via a *separate* .scoped() view
        # (see below), never by mutating this instance's company_id in
        # place - auth and user-management share the same underlying
        # dict/id-sequence but must never share a mutable company_id, since
        # a single request's dependency chain resolves get_current_user
        # (needs unscoped) before UserService's own company_id is even
        # known. AuthService.login is a third case, fitting neither: it
        # resolves its company fresh per call (from company_code) and
        # passes it explicitly to get_by_username_or_email below, never
        # touching self.company_id at all.
        self.company_id = company_id

    def scoped(self, company_id: int) -> "FakeUserRepository":
        """A company-scoped view over this same underlying storage.

        Sharing _by_id/_id_seq (not copying them) keeps a user created or
        looked up through the unscoped auth path and one created/listed
        through the scoped UserService path fully consistent - exactly
        like one real UserRepository and one real
        CompanyScopedRepository-based repository would, if both queried
        the same physical table.
        """
        view = FakeUserRepository.__new__(FakeUserRepository)
        view._by_id = self._by_id
        view._id_seq = self._id_seq
        view.company_id = company_id
        return view

    def _reindex(self, obj: User) -> None:
        self._by_id[obj.id] = obj

    def _in_scope(self, user: User) -> bool:
        return self.company_id is None or user.company_id == self.company_id

    def get_by_id(self, id_: int) -> User | None:
        user = self._by_id.get(id_)
        return user if user is not None and self._in_scope(user) else None

    def get_all(self) -> list[User]:
        return [u for u in self._by_id.values() if self._in_scope(u)]

    def get_by_email(self, email: str) -> User | None:
        target = email.strip().lower()
        return next(
            (u for u in self._by_id.values() if u.email.lower() == target and self._in_scope(u)),
            None,
        )

    def get_by_username(self, username: str) -> User | None:
        target = username.strip().lower()
        return next(
            (
                u
                for u in self._by_id.values()
                if u.username.lower() == target and self._in_scope(u)
            ),
            None,
        )

    def get_by_username_or_email(self, identifier: str, company_id: int) -> User | None:
        """Scoped by an explicit parameter, mirroring UserRepository's
        equivalent method - ignores self.company_id entirely, since
        AuthService.login resolves its company fresh on every call rather
        than at repository-construction time (see __init__'s docstring)."""
        target = identifier.strip().lower()
        return next(
            (
                u
                for u in self._by_id.values()
                if u.company_id == company_id
                and (u.username.lower() == target or u.email.lower() == target)
            ),
            None,
        )

    def _filtered(
        self,
        *,
        role_id: int | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[User]:
        results = [u for u in self._by_id.values() if self._in_scope(u)]
        if role_id is not None:
            results = [u for u in results if u.role_id == role_id]
        if department_id is not None:
            results = [u for u in results if u.department_id == department_id]
        if is_active is not None:
            results = [u for u in results if u.is_active == is_active]
        if search:
            needle = search.strip().lower()
            results = [
                u
                for u in results
                if needle in u.username.lower()
                or needle in u.first_name.lower()
                or needle in u.last_name.lower()
                or needle in u.email.lower()
            ]
        return sorted(results, key=lambda u: u.id)

    def get_with_filters(
        self,
        *,
        role_id: int | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        results = self._filtered(
            role_id=role_id, department_id=department_id, is_active=is_active, search=search
        )
        return results[skip : skip + limit]

    def count_with_filters(
        self,
        *,
        role_id: int | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> int:
        return len(
            self._filtered(
                role_id=role_id, department_id=department_id, is_active=is_active, search=search
            )
        )

    def create(self, obj: User) -> User:
        obj.id = self._id_seq[0]
        self._id_seq[0] += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._reindex(obj)
        return obj

    def update(self, obj: User) -> User:
        obj.updated_at = datetime.now(timezone.utc)
        self._reindex(obj)
        return obj


class FakeRoleRepository:
    """In-memory stand-in for RoleRepository. Same rationale as FakeUserRepository."""

    def __init__(self, roles: list[Role]) -> None:
        self._by_id = {role.id: role for role in roles}

    def get_by_id(self, id_: int) -> Role | None:
        return self._by_id.get(id_)

    def get_by_name(self, name: str) -> Role | None:
        return next((r for r in self._by_id.values() if r.name == name), None)


class FakeCompanyRepository:
    """In-memory stand-in for CompanyRepository. Same rationale as FakeUserRepository."""

    def __init__(self, companies: list[Company]) -> None:
        self._by_id = {company.id: company for company in companies}
        self._next_id = max(self._by_id, default=0) + 1

    def get_by_id(self, id_: int) -> Company | None:
        return self._by_id.get(id_)

    def get_by_code(self, company_code: str) -> Company | None:
        target = company_code.strip().lower()
        return next(
            (c for c in self._by_id.values() if c.company_code.lower() == target), None
        )

    def create(self, obj: Company) -> Company:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Company) -> Company:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj


class FakeCategoryRepository:
    """In-memory stand-in for CategoryRepository. Same rationale as FakeUserRepository."""

    def __init__(self, categories: list[Category] | None = None, company_id: int | None = None) -> None:
        self._by_id = {category.id: category for category in (categories or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.referenced_category_ids: set[int] = set()
        # None = unscoped (only test-local subclasses that never go through
        # the client fixture use this default); the client fixture's
        # per-request service overrides mutate this to the real caller's
        # company_id, mirroring the real CompanyScopedRepository.
        self.company_id = company_id

    def _in_scope(self, category: Category) -> bool:
        return self.company_id is None or category.company_id == self.company_id

    def get_all(self) -> list[Category]:
        return [c for c in self._by_id.values() if self._in_scope(c)]

    def get_by_id(self, id_: int) -> Category | None:
        category = self._by_id.get(id_)
        return category if category is not None and self._in_scope(category) else None

    def get_by_name(self, name: str) -> Category | None:
        target = name.strip().lower()
        return next(
            (
                c
                for c in self._by_id.values()
                if c.name.lower() == target and self._in_scope(c)
            ),
            None,
        )

    def create(self, obj: Category) -> Category:
        obj.id = self._next_id
        self._next_id += 1
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Category) -> Category:
        self._by_id[obj.id] = obj
        return obj

    def delete(self, obj: Category) -> None:
        self._by_id.pop(obj.id, None)

    def is_referenced_by_tickets(self, category_id: int) -> bool:
        return category_id in self.referenced_category_ids


class FakeInventoryCategoryRepository:
    """In-memory stand-in for InventoryCategoryRepository. Same rationale as
    FakeCategoryRepository."""

    def __init__(
        self,
        inventory_categories: list[InventoryCategory] | None = None,
        company_id: int | None = None,
    ) -> None:
        self._by_id = {c.id: c for c in (inventory_categories or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.company_id = company_id

    def _in_scope(self, category: InventoryCategory) -> bool:
        return self.company_id is None or category.company_id == self.company_id

    def get_all(self) -> list[InventoryCategory]:
        return [c for c in self._by_id.values() if self._in_scope(c)]

    def get_by_id(self, id_: int) -> InventoryCategory | None:
        category = self._by_id.get(id_)
        return category if category is not None and self._in_scope(category) else None

    def get_by_name(self, name: str) -> InventoryCategory | None:
        target = name.strip().lower()
        return next(
            (
                c
                for c in self._by_id.values()
                if c.name.lower() == target and self._in_scope(c)
            ),
            None,
        )

    def count_all(self) -> int:
        return len(self.get_all())

    def create(self, obj: InventoryCategory) -> InventoryCategory:
        obj.id = self._next_id
        self._next_id += 1
        obj.created_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: InventoryCategory) -> InventoryCategory:
        self._by_id[obj.id] = obj
        return obj


class FakeInventoryItemRepository:
    """In-memory stand-in for InventoryItemRepository. Same rationale as
    FakeTicketRepository - mirrors its real get_with_filters/
    count_with_filters semantics (search fields, low_stock,
    warranty_expiring_days, sortable-column allow-list) exactly, since the
    tests exercising filters/search/sort/pagination need faithful behavior,
    not just a passthrough.
    """

    _SORTABLE_KEYS: dict[str, Callable[["InventoryItem"], object]] = {
        "created_at": lambda i: i.created_at,
        "updated_at": lambda i: i.updated_at,
        "name": lambda i: i.name,
        "purchase_date": lambda i: i.purchase_date or date.min,
        "warranty_expiration": lambda i: i.warranty_expiration or date.min,
    }

    def __init__(
        self, items: list[InventoryItem] | None = None, company_id: int | None = None
    ) -> None:
        self._by_id = {i.id: i for i in (items or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.company_id = company_id

    def _in_scope(self, item: InventoryItem) -> bool:
        return self.company_id is None or item.company_id == self.company_id

    def get_by_id(self, id_: int) -> InventoryItem | None:
        item = self._by_id.get(id_)
        return item if item is not None and self._in_scope(item) else None

    def get_by_asset_tag(self, asset_tag: str) -> InventoryItem | None:
        target = asset_tag.strip().lower()
        return next(
            (
                i
                for i in self._by_id.values()
                if i.asset_tag is not None
                and i.asset_tag.lower() == target
                and self._in_scope(i)
            ),
            None,
        )

    def _filtered(
        self,
        *,
        inventory_category_id: int | None = None,
        tracking_type: InventoryTrackingType | None = None,
        status: InventoryStatus | None = None,
        condition: InventoryCondition | None = None,
        current_location_id: int | None = None,
        current_holder_user_id: int | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        search: str | None = None,
        low_stock: bool | None = None,
        warranty_expiring_days: int | None = None,
    ) -> list[InventoryItem]:
        results = [i for i in self._by_id.values() if self._in_scope(i)]
        if inventory_category_id is not None:
            results = [i for i in results if i.inventory_category_id == inventory_category_id]
        if tracking_type is not None:
            results = [i for i in results if i.tracking_type == tracking_type]
        if status is not None:
            results = [i for i in results if i.status == status]
        if condition is not None:
            results = [i for i in results if i.condition == condition]
        if current_location_id is not None:
            results = [i for i in results if i.current_location_id == current_location_id]
        if current_holder_user_id is not None:
            results = [i for i in results if i.current_holder_user_id == current_holder_user_id]
        if manufacturer:
            target = manufacturer.strip().lower()
            results = [
                i for i in results if (i.manufacturer or "").lower() == target
            ]
        if model:
            target = model.strip().lower()
            results = [i for i in results if (i.model or "").lower() == target]
        if search:
            needle = search.strip().lower()
            results = [
                i
                for i in results
                if needle in (i.name or "").lower()
                or needle in (i.asset_tag or "").lower()
                or needle in (i.serial_number or "").lower()
                or needle in (i.manufacturer or "").lower()
                or needle in (i.model or "").lower()
                or needle in (i.supplier or "").lower()
                or needle in (i.invoice_number or "").lower()
            ]
        if low_stock:
            results = [
                i
                for i in results
                if i.tracking_type == InventoryTrackingType.BULK
                and i.minimum_stock is not None
                and (i.stock_quantity - i.reserved_quantity) <= i.minimum_stock
            ]
        if warranty_expiring_days is not None:
            today = datetime.now(timezone.utc).date()
            horizon = today + timedelta(days=warranty_expiring_days)
            results = [
                i
                for i in results
                if i.warranty_expiration is not None and today <= i.warranty_expiration <= horizon
            ]
        return results

    def get_with_filters(
        self,
        *,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        skip: int | None = None,
        limit: int | None = None,
        **filters,
    ) -> list[InventoryItem]:
        results = self._filtered(**filters)
        key_fn = self._SORTABLE_KEYS.get(sort_by, self._SORTABLE_KEYS["created_at"])
        results = sorted(results, key=key_fn, reverse=(sort_dir != "asc"))
        if skip is not None:
            results = results[skip:]
        if limit is not None:
            results = results[:limit]
        return results

    def count_with_filters(self, **filters) -> int:
        return len(self._filtered(**filters))

    def create(self, obj: InventoryItem) -> InventoryItem:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: InventoryItem) -> InventoryItem:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj


class FakeTicketInventoryUsageRepository:
    """In-memory stand-in for TicketInventoryUsageRepository. Same rationale
    as FakeCommentRepository - starts empty, tests create whatever rows they
    need through the API (reserve/consume) rather than pre-seeded fixtures."""

    def __init__(
        self, usages: list[TicketInventoryUsage] | None = None, company_id: int | None = None
    ) -> None:
        self._by_id = {u.id: u for u in (usages or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.company_id = company_id

    def _in_scope(self, usage: TicketInventoryUsage) -> bool:
        return self.company_id is None or usage.company_id == self.company_id

    def get_by_id(self, id_: int) -> TicketInventoryUsage | None:
        usage = self._by_id.get(id_)
        return usage if usage is not None and self._in_scope(usage) else None

    def list_for_ticket(self, ticket_id: int) -> list[TicketInventoryUsage]:
        return sorted(
            (u for u in self._by_id.values() if u.ticket_id == ticket_id and self._in_scope(u)),
            key=lambda u: u.id,
        )

    def get_existing(self, ticket_id: int, inventory_item_id: int) -> TicketInventoryUsage | None:
        return next(
            (
                u
                for u in self._by_id.values()
                if u.ticket_id == ticket_id
                and u.inventory_item_id == inventory_item_id
                and self._in_scope(u)
            ),
            None,
        )

    def create(self, obj: TicketInventoryUsage) -> TicketInventoryUsage:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: TicketInventoryUsage) -> TicketInventoryUsage:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj

    def delete(self, obj: TicketInventoryUsage) -> None:
        self._by_id.pop(obj.id, None)


class FakeInventoryTransactionRepository:
    """In-memory stand-in for InventoryTransactionRepository. Same
    rationale as FakeTicketInventoryUsageRepository - starts empty, tests
    assert on rows written as a side effect of item/ticket-inventory
    mutations rather than pre-seeded fixtures. Deliberately has no
    update()/delete() - mirrors the real repository's append-only
    contract exactly."""

    def __init__(
        self, transactions: list[InventoryTransaction] | None = None, company_id: int | None = None
    ) -> None:
        self._by_id = {t.id: t for t in (transactions or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.company_id = company_id

    def _in_scope(self, transaction: InventoryTransaction) -> bool:
        return self.company_id is None or transaction.company_id == self.company_id

    def _filtered(
        self,
        *,
        inventory_item_id: int | None = None,
        ticket_id: int | None = None,
        transaction_type=None,
        performed_by_user_id: int | None = None,
    ) -> list[InventoryTransaction]:
        results = [t for t in self._by_id.values() if self._in_scope(t)]
        if inventory_item_id is not None:
            results = [t for t in results if t.inventory_item_id == inventory_item_id]
        if ticket_id is not None:
            results = [t for t in results if t.ticket_id == ticket_id]
        if transaction_type is not None:
            results = [t for t in results if t.transaction_type == transaction_type]
        if performed_by_user_id is not None:
            results = [t for t in results if t.performed_by_user_id == performed_by_user_id]
        return sorted(results, key=lambda t: t.id, reverse=True)

    def list_for_item(
        self, inventory_item_id: int, *, skip: int = 0, limit: int = 100
    ) -> list[InventoryTransaction]:
        results = self._filtered(inventory_item_id=inventory_item_id)
        return results[skip : skip + limit]

    def count_for_item(self, inventory_item_id: int) -> int:
        return len(self._filtered(inventory_item_id=inventory_item_id))

    def list_company_transactions(
        self,
        *,
        inventory_item_id: int | None = None,
        ticket_id: int | None = None,
        transaction_type=None,
        performed_by_user_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[InventoryTransaction]:
        results = self._filtered(
            inventory_item_id=inventory_item_id,
            ticket_id=ticket_id,
            transaction_type=transaction_type,
            performed_by_user_id=performed_by_user_id,
        )
        return results[skip : skip + limit]

    def count_company_transactions(
        self,
        *,
        inventory_item_id: int | None = None,
        ticket_id: int | None = None,
        transaction_type=None,
        performed_by_user_id: int | None = None,
    ) -> int:
        return len(
            self._filtered(
                inventory_item_id=inventory_item_id,
                ticket_id=ticket_id,
                transaction_type=transaction_type,
                performed_by_user_id=performed_by_user_id,
            )
        )

    def create(self, obj: InventoryTransaction) -> InventoryTransaction:
        obj.id = self._next_id
        self._next_id += 1
        obj.created_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj


class FakeDepartmentRepository:
    """In-memory stand-in for DepartmentRepository. Same rationale as FakeCategoryRepository."""

    def __init__(
        self, departments: list[Department] | None = None, company_id: int | None = None
    ) -> None:
        self._by_id = {department.id: department for department in (departments or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.company_id = company_id

    def _in_scope(self, department: Department) -> bool:
        return self.company_id is None or department.company_id == self.company_id

    def get_all(self) -> list[Department]:
        return [d for d in self._by_id.values() if self._in_scope(d)]

    def get_by_id(self, id_: int) -> Department | None:
        department = self._by_id.get(id_)
        return department if department is not None and self._in_scope(department) else None

    def get_by_title(self, title: str) -> Department | None:
        target = title.strip().lower()
        return next(
            (
                d
                for d in self._by_id.values()
                if d.title.lower() == target and self._in_scope(d)
            ),
            None,
        )

    def create(self, obj: Department) -> Department:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Department) -> Department:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj


class FakeLocationRepository:
    """In-memory stand-in for LocationRepository. Same rationale as FakeCategoryRepository."""

    def __init__(
        self, locations: list[Location] | None = None, company_id: int | None = None
    ) -> None:
        self._by_id = {location.id: location for location in (locations or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.company_id = company_id

    def _in_scope(self, location: Location) -> bool:
        return self.company_id is None or location.company_id == self.company_id

    def get_all(self) -> list[Location]:
        return [loc for loc in self._by_id.values() if self._in_scope(loc)]

    def get_by_id(self, id_: int) -> Location | None:
        location = self._by_id.get(id_)
        return location if location is not None and self._in_scope(location) else None

    def get_by_title(self, title: str) -> Location | None:
        target = title.strip().lower()
        return next(
            (
                loc
                for loc in self._by_id.values()
                if loc.title.lower() == target and self._in_scope(loc)
            ),
            None,
        )

    def create(self, obj: Location) -> Location:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Location) -> Location:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj


class FakePriorityRepository:
    """In-memory stand-in for PriorityRepository. Same rationale as FakeCategoryRepository."""

    def __init__(
        self, priorities: list[Priority] | None = None, company_id: int | None = None
    ) -> None:
        self._by_id = {priority.id: priority for priority in (priorities or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.company_id = company_id

    def _in_scope(self, priority: Priority) -> bool:
        return self.company_id is None or priority.company_id == self.company_id

    def get_all(self) -> list[Priority]:
        return [p for p in self._by_id.values() if self._in_scope(p)]

    def get_by_id(self, id_: int) -> Priority | None:
        priority = self._by_id.get(id_)
        return priority if priority is not None and self._in_scope(priority) else None

    def get_by_title(self, title: str) -> Priority | None:
        target = title.strip().lower()
        return next(
            (
                p
                for p in self._by_id.values()
                if p.title.lower() == target and self._in_scope(p)
            ),
            None,
        )

    def create(self, obj: Priority) -> Priority:
        obj.id = self._next_id
        self._next_id += 1
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Priority) -> Priority:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj


class FakeTicketRepository:
    """In-memory stand-in for TicketRepository. Same rationale as FakeCategoryRepository."""

    _SORT_KEYS: dict[str, Callable[[Ticket], object]] = {
        "created_at": lambda t: t.created_at,
        "updated_at": lambda t: t.updated_at,
        "title": lambda t: t.title,
        "ticket_number": lambda t: t.ticket_number,
    }

    def __init__(self, tickets: list[Ticket] | None = None, company_id: int | None = None) -> None:
        self._by_id = {ticket.id: ticket for ticket in (tickets or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.fail_next_create = False
        self.company_id = company_id

    def _in_scope(self, ticket: Ticket) -> bool:
        return self.company_id is None or ticket.company_id == self.company_id

    def get_by_id(self, id_: int) -> Ticket | None:
        ticket = self._by_id.get(id_)
        return ticket if ticket is not None and self._in_scope(ticket) else None

    def get_with_filters(
        self,
        *,
        status: TicketStatus | None = None,
        priority_id: int | None = None,
        category_id: int | None = None,
        department_id: int | None = None,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        skip: int | None = None,
        limit: int | None = None,
    ) -> list[Ticket]:
        results = [t for t in self._by_id.values() if self._in_scope(t)]
        if department_id is not None:
            results = [
                t
                for t in results
                if t.created_by is not None and t.created_by.department_id == department_id
            ]
        if status is not None:
            results = [t for t in results if t.status == status]
        if priority_id is not None:
            results = [t for t in results if t.priority_id == priority_id]
        if category_id is not None:
            results = [t for t in results if t.category_id == category_id]
        if created_by_user_id is not None:
            results = [t for t in results if t.created_by_user_id == created_by_user_id]
        if assigned_technician_id is not None:
            results = [t for t in results if t.assigned_technician_id == assigned_technician_id]
        if search:
            needle = search.strip().lower()
            results = [
                t
                for t in results
                if needle in t.title.lower() or needle in t.description.lower()
            ]

        key_fn = self._SORT_KEYS.get(sort_by, self._SORT_KEYS["created_at"])
        results = sorted(results, key=key_fn, reverse=(sort_dir != "asc"))

        if skip is not None:
            results = results[skip:]
        if limit is not None:
            results = results[:limit]
        return results

    def create(self, obj: Ticket) -> Ticket:
        if self.fail_next_create:
            self.fail_next_create = False
            raise IntegrityError("insert", {}, Exception("duplicate ticket_number"))
        obj.id = self._next_id
        self._next_id += 1
        # A real INSERT would populate these via server_default=func.now();
        # an unsaved Python object has neither until "written".
        now = datetime.now(timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Ticket) -> Ticket:
        obj.updated_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj

    def delete(self, obj: Ticket) -> None:
        self._by_id.pop(obj.id, None)

    def count_for_year(self, year: int) -> int:
        prefix = f"IT-{year}-"
        return sum(
            1
            for t in self._by_id.values()
            if t.ticket_number.startswith(prefix) and self._in_scope(t)
        )

    # ---- analytics aggregates (mirrors TicketRepository's SQL exactly in
    # pure Python) --------------------------------------------------------

    def _scoped(
        self, created_by_user_id: int | None, assigned_technician_id: int | None
    ) -> list[Ticket]:
        results = [t for t in self._by_id.values() if self._in_scope(t)]
        if created_by_user_id is not None:
            results = [t for t in results if t.created_by_user_id == created_by_user_id]
        if assigned_technician_id is not None:
            results = [t for t in results if t.assigned_technician_id == assigned_technician_id]
        return results

    def count_grouped_by_status(
        self, *, created_by_user_id: int | None = None, assigned_technician_id: int | None = None
    ) -> dict[TicketStatus, int]:
        counts: dict[TicketStatus, int] = {}
        for t in self._scoped(created_by_user_id, assigned_technician_id):
            counts[t.status] = counts.get(t.status, 0) + 1
        return counts

    def count_grouped_by_priority(
        self, *, created_by_user_id: int | None = None, assigned_technician_id: int | None = None
    ) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for t in self._scoped(created_by_user_id, assigned_technician_id):
            if t.priority is not None and t.priority.company_id == self.company_id:
                counts[t.priority.title] = counts.get(t.priority.title, 0) + 1
        return list(counts.items())

    def count_grouped_by_category(
        self, *, created_by_user_id: int | None = None, assigned_technician_id: int | None = None
    ) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for t in self._scoped(created_by_user_id, assigned_technician_id):
            if t.category is not None and t.category.company_id == self.company_id:
                counts[t.category.name] = counts.get(t.category.name, 0) + 1
        return list(counts.items())

    def count_high_priority_open(
        self, *, created_by_user_id: int | None = None, assigned_technician_id: int | None = None
    ) -> int:
        terminal = {TicketStatus.RESOLVED, TicketStatus.CLOSED}
        return sum(
            1
            for t in self._scoped(created_by_user_id, assigned_technician_id)
            if t.priority is not None
            and t.priority.company_id == self.company_id
            and t.priority.title in ("High", "Critical")
            and t.status not in terminal
        )

    def count_unassigned(self) -> int:
        return sum(
            1
            for t in self._by_id.values()
            if self._in_scope(t)
            and t.status == TicketStatus.NEW
            and t.assigned_technician_id is None
        )

    def avg_resolution_minutes(
        self, *, created_by_user_id: int | None = None, assigned_technician_id: int | None = None
    ) -> float | None:
        durations = [
            (t.resolved_at - t.created_at).total_seconds() / 60
            for t in self._scoped(created_by_user_id, assigned_technician_id)
            if t.resolved_at is not None
        ]
        return sum(durations) / len(durations) if durations else None

    def _count_by_boundaries(
        self,
        date_attr: str,
        boundaries: list[tuple[datetime, datetime]],
        created_by_user_id: int | None,
        assigned_technician_id: int | None,
    ) -> list[int]:
        counts = [0] * len(boundaries)
        for t in self._scoped(created_by_user_id, assigned_technician_id):
            value = getattr(t, date_attr)
            if value is None:
                continue
            for i, (start, end) in enumerate(boundaries):
                if start <= value < end:
                    counts[i] += 1
                    break
        return counts

    def count_created_by_boundaries(
        self,
        boundaries: list[tuple[datetime, datetime]],
        *,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> list[int]:
        return self._count_by_boundaries(
            "created_at", boundaries, created_by_user_id, assigned_technician_id
        )

    def count_resolved_by_boundaries(
        self,
        boundaries: list[tuple[datetime, datetime]],
        *,
        created_by_user_id: int | None = None,
        assigned_technician_id: int | None = None,
    ) -> list[int]:
        return self._count_by_boundaries(
            "resolved_at", boundaries, created_by_user_id, assigned_technician_id
        )


class FakeCommentRepository:
    """In-memory stand-in for CommentRepository. Same rationale as FakeTicketRepository."""

    def __init__(self, comments: list[Comment] | None = None, company_id: int | None = None) -> None:
        self._by_id = {comment.id: comment for comment in (comments or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.company_id = company_id

    def _in_scope(self, comment: Comment) -> bool:
        return self.company_id is None or comment.company_id == self.company_id

    def get_by_id(self, id_: int) -> Comment | None:
        comment = self._by_id.get(id_)
        return comment if comment is not None and self._in_scope(comment) else None

    def list_for_ticket(self, ticket_id: int) -> list[Comment]:
        return [
            c for c in self._by_id.values() if c.ticket_id == ticket_id and self._in_scope(c)
        ]

    def create(self, obj: Comment) -> Comment:
        obj.id = self._next_id
        self._next_id += 1
        # A real INSERT would populate this via CreatedAtMixin's
        # server_default=func.now(); updated_at stays None until an edit,
        # matching the model exactly (no server default/onupdate on it).
        obj.created_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj

    def update(self, obj: Comment) -> Comment:
        self._by_id[obj.id] = obj
        return obj

    def delete(self, obj: Comment) -> None:
        self._by_id.pop(obj.id, None)


class FakeHistoryRepository:
    """In-memory stand-in for HistoryRepository. Same rationale as the others."""

    def __init__(self, company_id: int | None = None) -> None:
        self._entries: list[TicketHistory] = []
        self._next_id = 1
        self.company_id = company_id

    def create(self, obj: TicketHistory) -> TicketHistory:
        obj.id = self._next_id
        self._next_id += 1
        obj.created_at = datetime.now(timezone.utc)
        self._entries.append(obj)
        return obj

    def list_for_ticket(self, ticket_id: int) -> list[TicketHistory]:
        return [
            e
            for e in self._entries
            if e.ticket_id == ticket_id
            and (self.company_id is None or e.company_id == self.company_id)
        ]


class FakeAttachmentRepository:
    """In-memory stand-in for AttachmentRepository. Same rationale as the others."""

    def __init__(
        self, attachments: list[Attachment] | None = None, company_id: int | None = None
    ) -> None:
        self._by_id = {a.id: a for a in (attachments or [])}
        self._next_id = max(self._by_id, default=0) + 1
        self.company_id = company_id

    def _in_scope(self, attachment: Attachment) -> bool:
        return self.company_id is None or attachment.company_id == self.company_id

    def get_by_id(self, id_: int) -> Attachment | None:
        attachment = self._by_id.get(id_)
        return attachment if attachment is not None and self._in_scope(attachment) else None

    def list_for_ticket(self, ticket_id: int) -> list[Attachment]:
        return [
            a for a in self._by_id.values() if a.ticket_id == ticket_id and self._in_scope(a)
        ]

    def create(self, obj: Attachment) -> Attachment:
        obj.id = self._next_id
        self._next_id += 1
        obj.created_at = datetime.now(timezone.utc)
        self._by_id[obj.id] = obj
        return obj

    def delete(self, obj: Attachment) -> None:
        self._by_id.pop(obj.id, None)


class FakeStorageService:
    """In-memory stand-in for StorageService - no real filesystem access.

    AttachmentService only calls a few narrow methods, so a dict-backed
    double is enough to exercise upload/download/delete without touching
    disk during the API test suite. Real filesystem behavior (including
    path-traversal defense) is covered separately in test_storage_service.py
    against a real temp directory.
    """

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self._counter = 0

    def generate_stored_filename(self, original_filename: str) -> str:
        extension = Path(original_filename or "").suffix.lower()
        self._counter += 1
        return f"fake-{self._counter}{extension}"

    def save(self, stored_filename: str, content: bytes) -> None:
        self.files[stored_filename] = content

    def load(self, stored_filename: str) -> bytes:
        return self.files[stored_filename]

    def delete(self, stored_filename: str) -> None:
        self.files.pop(stored_filename, None)


class FakeSession:
    """No-op stand-in for the transaction-boundary calls the services make.

    CategoryService/TicketService/CommentService/UserService/etc. own
    commit()/rollback() (repositories never commit), so a fake service
    needs a fake session to call those on - this just swallows both, since
    the fake repositories already persist in memory.
    """

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


@pytest.fixture
def admin_role() -> Role:
    """The Company Administrator role - any number of users may hold it per
    company, all with identical permissions (see active_admin_user and
    active_manager_user, two distinct users sharing this same role)."""
    return Role(
        id=1, name="Company Administrator", description="Full access within their own company"
    )


@pytest.fixture
def employee_role() -> Role:
    return Role(id=2, name="Employee", description="Reports tickets")


@pytest.fixture
def technician_role() -> Role:
    return Role(id=3, name="Technician", description="Resolves tickets")


@pytest.fixture
def system_administrator_role() -> Role:
    """Platform-level role, not yet backed by any seeded user or reachable
    route (see the role-consolidation migration's docstring) - included here
    only so the fake role_repository mirrors the real roles table's final
    4-role shape."""
    return Role(
        id=4, name="System Administrator", description="Platform-level access; not yet in use"
    )


@pytest.fixture
def company_a() -> Company:
    now = datetime.now(timezone.utc)
    return Company(
        id=COMPANY_A_ID,
        name="Company A",
        company_code=COMPANY_A_CODE,
        theme="light",
        timezone="UTC",
        language="en",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def company_b() -> Company:
    now = datetime.now(timezone.utc)
    return Company(
        id=COMPANY_B_ID,
        name="Company B",
        company_code=COMPANY_B_CODE,
        theme="light",
        timezone="UTC",
        language="en",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def suspended_company() -> Company:
    """A real, existing company whose account has been suspended - used to
    prove login and every authenticated request reject it distinctly, not
    just at the moment of suspension but for every request afterward, even
    ones carrying an already-issued, still-unexpired access token."""
    now = datetime.now(timezone.utc)
    return Company(
        id=SUSPENDED_COMPANY_ID,
        name="Suspended Company",
        company_code=SUSPENDED_COMPANY_CODE,
        theme="light",
        timezone="UTC",
        language="en",
        is_active=False,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def it_department() -> Department:
    now = datetime.now(timezone.utc)
    return Department(id=1, company_id=COMPANY_A_ID, title="IT", created_at=now, updated_at=now)


@pytest.fixture
def hr_department() -> Department:
    now = datetime.now(timezone.utc)
    return Department(id=2, company_id=COMPANY_A_ID, title="HR", created_at=now, updated_at=now)


@pytest.fixture
def low_priority() -> Priority:
    now = datetime.now(timezone.utc)
    return Priority(id=1, company_id=COMPANY_A_ID, title="Low", created_at=now, updated_at=now)


@pytest.fixture
def medium_priority() -> Priority:
    now = datetime.now(timezone.utc)
    return Priority(id=2, company_id=COMPANY_A_ID, title="Medium", created_at=now, updated_at=now)


@pytest.fixture
def high_priority() -> Priority:
    now = datetime.now(timezone.utc)
    return Priority(id=3, company_id=COMPANY_A_ID, title="High", created_at=now, updated_at=now)


@pytest.fixture
def critical_priority() -> Priority:
    now = datetime.now(timezone.utc)
    return Priority(id=4, company_id=COMPANY_A_ID, title="Critical", created_at=now, updated_at=now)


@pytest.fixture
def head_office_location() -> Location:
    now = datetime.now(timezone.utc)
    return Location(
        id=1,
        company_id=COMPANY_A_ID,
        title="Head Office - Floor 2",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def branch_office_location() -> Location:
    now = datetime.now(timezone.utc)
    return Location(
        id=2,
        company_id=COMPANY_A_ID,
        title="Branch Office",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def inactive_location() -> Location:
    """A retired location - no longer selectable, but a ticket may still reference it."""
    now = datetime.now(timezone.utc)
    return Location(
        id=3,
        company_id=COMPANY_A_ID,
        title="Old Warehouse",
        is_active=False,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def active_admin_user(admin_role: Role, it_department: Department, company_a: Company) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=1,
        company_id=COMPANY_A_ID,
        username="admin",
        first_name="Ada",
        last_name="Admin",
        email="admin@itonit.test",
        password_hash=hash_password(ADMIN_PASSWORD),
        role_id=admin_role.id,
        department_id=it_department.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = admin_role
    user.department = it_department
    user.company = company_a
    return user


@pytest.fixture
def inactive_user(employee_role: Role, company_a: Company) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=2,
        company_id=COMPANY_A_ID,
        username="inactive",
        first_name="Ivy",
        last_name="Inactive",
        email="inactive@itonit.test",
        password_hash=hash_password(INACTIVE_PASSWORD),
        role_id=employee_role.id,
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    user.role = employee_role
    user.department = None
    user.company = company_a
    return user


@pytest.fixture
def active_employee_user(
    employee_role: Role, it_department: Department, company_a: Company
) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=3,
        company_id=COMPANY_A_ID,
        username="employee",
        first_name="Eve",
        last_name="Employee",
        email="employee@itonit.test",
        password_hash=hash_password(EMPLOYEE_PASSWORD),
        role_id=employee_role.id,
        department_id=it_department.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = employee_role
    user.department = it_department
    user.company = company_a
    return user


@pytest.fixture
def active_technician_user(technician_role: Role, company_a: Company) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=4,
        company_id=COMPANY_A_ID,
        username="technician",
        first_name="Tom",
        last_name="Technician",
        email="technician@itonit.test",
        password_hash=hash_password(TECHNICIAN_PASSWORD),
        role_id=technician_role.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = technician_role
    user.department = None
    user.company = company_a
    return user


@pytest.fixture
def active_manager_user(admin_role: Role, company_a: Company) -> User:
    """A second Company Administrator, distinct from active_admin_user -
    Company Administrator is not a singular role (any number may exist per
    company, all with identical permissions), so this fixture is kept
    (rather than deleted along with the retired Manager role) specifically
    to exercise that. The fixture/variable name is a historical holdover
    from before the Manager+Administrator merge - only its role changed.
    """
    now = datetime.now(timezone.utc)
    user = User(
        id=5,
        company_id=COMPANY_A_ID,
        username="manager",
        first_name="Mona",
        last_name="Manager",
        email="manager@itonit.test",
        password_hash=hash_password(MANAGER_PASSWORD),
        role_id=admin_role.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = admin_role
    user.department = None
    user.company = company_a
    return user


@pytest.fixture
def active_employee_user_2(
    employee_role: Role, hr_department: Department, company_a: Company
) -> User:
    """A second employee, distinct from active_employee_user - needed to
    prove employees cannot see/edit each other's tickets."""
    now = datetime.now(timezone.utc)
    user = User(
        id=6,
        company_id=COMPANY_A_ID,
        username="employee2",
        first_name="Eli",
        last_name="EmployeeTwo",
        email="employee2@itonit.test",
        password_hash=hash_password(EMPLOYEE_2_PASSWORD),
        role_id=employee_role.id,
        department_id=hr_department.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = employee_role
    user.department = hr_department
    user.company = company_a
    return user


@pytest.fixture
def active_technician_user_2(technician_role: Role, company_a: Company) -> User:
    """A second technician, distinct from active_technician_user - needed to
    prove technicians cannot see/edit tickets assigned to someone else."""
    now = datetime.now(timezone.utc)
    user = User(
        id=7,
        company_id=COMPANY_A_ID,
        username="technician2",
        first_name="Tia",
        last_name="TechnicianTwo",
        email="technician2@itonit.test",
        password_hash=hash_password(TECHNICIAN_2_PASSWORD),
        role_id=technician_role.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = technician_role
    user.department = None
    user.company = company_a
    return user


@pytest.fixture
def admin_password() -> str:
    return ADMIN_PASSWORD


@pytest.fixture
def inactive_password() -> str:
    return INACTIVE_PASSWORD


@pytest.fixture
def hardware_category() -> Category:
    return Category(
        id=1, company_id=COMPANY_A_ID, name="Hardware", description="Physical equipment issues"
    )


@pytest.fixture
def software_category() -> Category:
    return Category(
        id=2, company_id=COMPANY_A_ID, name="Software", description="Application issues"
    )


@pytest.fixture
def employee_ticket(
    hardware_category: Category,
    medium_priority: Priority,
    head_office_location: Location,
    active_employee_user: User,
) -> Ticket:
    """A brand-new ticket, owned by active_employee_user, not yet assigned."""
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=1,
        company_id=COMPANY_A_ID,
        ticket_number="IT-2026-000001",
        title="Laptop will not boot",
        description="Screen stays black after pressing the power button.",
        location_id=head_office_location.id,
        status=TicketStatus.NEW,
        priority_id=medium_priority.id,
        category_id=hardware_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=None,
        created_at=now,
        updated_at=now,
    )
    ticket.category = hardware_category
    ticket.priority = medium_priority
    ticket.location = head_office_location
    ticket.created_by = active_employee_user
    ticket.assigned_technician = None
    return ticket


@pytest.fixture
def assigned_ticket(
    software_category: Category,
    high_priority: Priority,
    active_employee_user: User,
    active_technician_user: User,
) -> Ticket:
    """A ticket already assigned to active_technician_user and in progress."""
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=2,
        company_id=COMPANY_A_ID,
        ticket_number="IT-2026-000002",
        title="VPN disconnects repeatedly",
        description="The VPN client drops the connection every few minutes.",
        location_id=None,
        status=TicketStatus.ASSIGNED,
        priority_id=high_priority.id,
        category_id=software_category.id,
        created_by_user_id=active_employee_user.id,
        assigned_technician_id=active_technician_user.id,
        created_at=now,
        updated_at=now,
    )
    ticket.category = software_category
    ticket.priority = high_priority
    ticket.created_by = active_employee_user
    ticket.assigned_technician = active_technician_user
    return ticket


@pytest.fixture
def employee_comment(employee_ticket: Ticket, active_employee_user: User) -> Comment:
    """A comment authored by active_employee_user on their own ticket."""
    comment = Comment(
        id=1,
        company_id=COMPANY_A_ID,
        ticket_id=employee_ticket.id,
        author_user_id=active_employee_user.id,
        content="Initial comment from the employee.",
        created_at=datetime.now(timezone.utc),
    )
    comment.author = active_employee_user
    return comment


@pytest.fixture
def assigned_ticket_comment(assigned_ticket: Ticket, active_employee_user: User) -> Comment:
    """A comment on assigned_ticket, authored by the employee who created it.

    active_technician_user can also view assigned_ticket (it's assigned to
    them), so this fixture lets tests distinguish "blocked at the ticket
    view gate" from "blocked at comment ownership specifically" - both the
    employee and the technician can see this comment, but only the employee
    authored it.
    """
    comment = Comment(
        id=2,
        company_id=COMPANY_A_ID,
        ticket_id=assigned_ticket.id,
        author_user_id=active_employee_user.id,
        content="Employee's comment on the assigned ticket.",
        created_at=datetime.now(timezone.utc),
    )
    comment.author = active_employee_user
    return comment


@pytest.fixture
def employee_attachment(employee_ticket: Ticket, active_employee_user: User) -> Attachment:
    """An attachment on employee_ticket, uploaded by active_employee_user."""
    attachment = Attachment(
        id=1,
        company_id=COMPANY_A_ID,
        ticket_id=employee_ticket.id,
        uploaded_by_user_id=active_employee_user.id,
        original_filename="screenshot.png",
        stored_filename="existing-file.png",
        file_path="existing-file.png",
        content_type="image/png",
        file_size=17,
        created_at=datetime.now(timezone.utc),
    )
    attachment.uploaded_by = active_employee_user
    return attachment


# ---------------------------------------------------------------------------
# Company B fixtures - a second tenant, coexisting in the same fake
# repositories as the Company A fixtures above. Their sole purpose is
# proving cross-company isolation: every cross-company test needs a real,
# existing "other company" row to prove a Company A query excludes it.
# ---------------------------------------------------------------------------


@pytest.fixture
def company_b_department() -> Department:
    now = datetime.now(timezone.utc)
    return Department(
        id=101, company_id=COMPANY_B_ID, title="Support", created_at=now, updated_at=now
    )


@pytest.fixture
def company_b_priority() -> Priority:
    now = datetime.now(timezone.utc)
    return Priority(
        id=101, company_id=COMPANY_B_ID, title="Urgent", created_at=now, updated_at=now
    )


@pytest.fixture
def company_b_location() -> Location:
    now = datetime.now(timezone.utc)
    return Location(
        id=101,
        company_id=COMPANY_B_ID,
        title="Company B HQ",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def company_b_category() -> Category:
    return Category(
        id=101,
        company_id=COMPANY_B_ID,
        name="Networking",
        description="Company B's own category",
    )


@pytest.fixture
def company_b_admin_user(
    admin_role: Role, company_b_department: Department, company_b: Company
) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=101,
        company_id=COMPANY_B_ID,
        username="companyb_admin",
        first_name="Beatrix",
        last_name="Admin",
        email="admin@companyb.test",
        password_hash=hash_password(COMPANY_B_ADMIN_PASSWORD),
        role_id=admin_role.id,
        department_id=company_b_department.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = admin_role
    user.department = company_b_department
    user.company = company_b
    return user


@pytest.fixture
def company_b_technician_user(technician_role: Role, company_b: Company) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=102,
        company_id=COMPANY_B_ID,
        username="companyb_technician",
        first_name="Bruno",
        last_name="Technician",
        email="technician@companyb.test",
        password_hash=hash_password(COMPANY_B_TECHNICIAN_PASSWORD),
        role_id=technician_role.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = technician_role
    user.department = None
    user.company = company_b
    return user


@pytest.fixture
def company_b_employee_user(
    employee_role: Role, company_b_department: Department, company_b: Company
) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=103,
        company_id=COMPANY_B_ID,
        username="companyb_employee",
        first_name="Bianca",
        last_name="Employee",
        email="employee@companyb.test",
        password_hash=hash_password(COMPANY_B_EMPLOYEE_PASSWORD),
        role_id=employee_role.id,
        department_id=company_b_department.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user.role = employee_role
    user.department = company_b_department
    user.company = company_b
    return user


@pytest.fixture
def company_b_ticket(
    company_b_category: Category,
    company_b_priority: Priority,
    company_b_location: Location,
    company_b_employee_user: User,
    company_b_technician_user: User,
) -> Ticket:
    """A ticket entirely owned by Company B - created by its employee,
    assigned to its technician. No relationship to any Company A row."""
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=101,
        company_id=COMPANY_B_ID,
        ticket_number="IT-2026-000001",
        title="Company B printer offline",
        description="The office printer on floor 1 is unreachable.",
        location_id=company_b_location.id,
        status=TicketStatus.ASSIGNED,
        priority_id=company_b_priority.id,
        category_id=company_b_category.id,
        created_by_user_id=company_b_employee_user.id,
        assigned_technician_id=company_b_technician_user.id,
        created_at=now,
        updated_at=now,
    )
    ticket.category = company_b_category
    ticket.priority = company_b_priority
    ticket.location = company_b_location
    ticket.created_by = company_b_employee_user
    ticket.assigned_technician = company_b_technician_user
    return ticket


@pytest.fixture
def company_b_comment(company_b_ticket: Ticket, company_b_employee_user: User) -> Comment:
    """A comment on Company B's own ticket, authored by its own employee."""
    comment = Comment(
        id=101,
        company_id=COMPANY_B_ID,
        ticket_id=company_b_ticket.id,
        author_user_id=company_b_employee_user.id,
        content="Company B's own comment.",
        created_at=datetime.now(timezone.utc),
    )
    comment.author = company_b_employee_user
    return comment


@pytest.fixture
def company_b_attachment(company_b_ticket: Ticket, company_b_employee_user: User) -> Attachment:
    """An attachment on Company B's own ticket."""
    attachment = Attachment(
        id=101,
        company_id=COMPANY_B_ID,
        ticket_id=company_b_ticket.id,
        uploaded_by_user_id=company_b_employee_user.id,
        original_filename="company-b-photo.png",
        stored_filename="company-b-existing-file.png",
        file_path="company-b-existing-file.png",
        content_type="image/png",
        file_size=23,
        created_at=datetime.now(timezone.utc),
    )
    attachment.uploaded_by = company_b_employee_user
    return attachment


@pytest.fixture
def user_repository(
    active_admin_user: User,
    inactive_user: User,
    active_employee_user: User,
    active_technician_user: User,
    active_manager_user: User,
    active_employee_user_2: User,
    active_technician_user_2: User,
    company_b_admin_user: User,
    company_b_technician_user: User,
    company_b_employee_user: User,
) -> FakeUserRepository:
    # Unscoped (company_id=None) - both companies' users physically coexist
    # here, exactly as they would in one real `users` table. Scoping is
    # applied per-request, not by excluding rows at fixture time (see the
    # client fixture's _user_service override).
    return FakeUserRepository(
        [
            active_admin_user,
            inactive_user,
            active_employee_user,
            active_technician_user,
            active_manager_user,
            active_employee_user_2,
            active_technician_user_2,
            company_b_admin_user,
            company_b_technician_user,
            company_b_employee_user,
        ]
    )


@pytest.fixture
def role_repository(
    admin_role: Role,
    employee_role: Role,
    technician_role: Role,
    system_administrator_role: Role,
) -> FakeRoleRepository:
    return FakeRoleRepository(
        [admin_role, employee_role, technician_role, system_administrator_role]
    )


@pytest.fixture
def company_repository(
    company_a: Company, company_b: Company, suspended_company: Company
) -> FakeCompanyRepository:
    return FakeCompanyRepository([company_a, company_b, suspended_company])


@pytest.fixture
def department_repository(
    it_department: Department, hr_department: Department, company_b_department: Department
) -> FakeDepartmentRepository:
    return FakeDepartmentRepository([it_department, hr_department, company_b_department])


@pytest.fixture
def priority_repository(
    low_priority: Priority,
    medium_priority: Priority,
    high_priority: Priority,
    critical_priority: Priority,
    company_b_priority: Priority,
) -> FakePriorityRepository:
    return FakePriorityRepository(
        [low_priority, medium_priority, high_priority, critical_priority, company_b_priority]
    )


@pytest.fixture
def location_repository(
    head_office_location: Location,
    branch_office_location: Location,
    inactive_location: Location,
    company_b_location: Location,
) -> FakeLocationRepository:
    return FakeLocationRepository(
        [head_office_location, branch_office_location, inactive_location, company_b_location]
    )


@pytest.fixture
def category_repository(
    hardware_category: Category, software_category: Category, company_b_category: Category
) -> FakeCategoryRepository:
    return FakeCategoryRepository([hardware_category, software_category, company_b_category])


@pytest.fixture
def inventory_category_repository() -> FakeInventoryCategoryRepository:
    """Starts empty - no test needs a pre-existing inventory category
    fixture the way category_repository needs hardware_category (referenced
    by ticket fixtures). Registration tests populate this via
    CompanyService._seed_defaults; inventory item tests that need a
    category create one directly against this fake (see
    test_inventory_items.py's own local fixtures) rather than this fixture
    pre-loading fixed rows - keeping it empty by default is load-bearing
    for test_register_company_seeds_eleven_starter_inventory_categories,
    which asserts on everything present in it."""
    return FakeInventoryCategoryRepository()


@pytest.fixture
def inventory_item_repository() -> FakeInventoryItemRepository:
    """Starts empty - inventory item tests create whatever rows they need
    directly against this fake (and against inventory_category_repository/
    location_repository/user_repository for references), same rationale as
    inventory_category_repository above."""
    return FakeInventoryItemRepository()


@pytest.fixture
def ticket_repository(
    employee_ticket: Ticket, assigned_ticket: Ticket, company_b_ticket: Ticket
) -> FakeTicketRepository:
    return FakeTicketRepository([employee_ticket, assigned_ticket, company_b_ticket])


@pytest.fixture
def ticket_inventory_usage_repository() -> FakeTicketInventoryUsageRepository:
    """Starts empty - tests create rows via the reserve endpoint rather than
    pre-seeded fixtures, same rationale as inventory_item_repository."""
    return FakeTicketInventoryUsageRepository()


@pytest.fixture
def inventory_transaction_repository() -> FakeInventoryTransactionRepository:
    """Starts empty - tests assert on rows written as a side effect of
    item/ticket-inventory mutations rather than pre-seeded fixtures, same
    rationale as ticket_inventory_usage_repository."""
    return FakeInventoryTransactionRepository()


@pytest.fixture
def comment_repository(
    employee_comment: Comment, assigned_ticket_comment: Comment, company_b_comment: Comment
) -> FakeCommentRepository:
    return FakeCommentRepository([employee_comment, assigned_ticket_comment, company_b_comment])


@pytest.fixture
def history_repository() -> FakeHistoryRepository:
    return FakeHistoryRepository()


@pytest.fixture
def storage_service() -> FakeStorageService:
    return FakeStorageService()


@pytest.fixture
def attachment_repository(
    employee_attachment: Attachment,
    company_b_attachment: Attachment,
    storage_service: FakeStorageService,
) -> FakeAttachmentRepository:
    # Pre-populate the fake filesystem so a download of either fixture
    # attachment (created outside any upload call) has real bytes to return.
    storage_service.files[employee_attachment.file_path] = b"fake-png-bytes"
    storage_service.files[company_b_attachment.file_path] = b"fake-company-b-png-bytes"
    return FakeAttachmentRepository([employee_attachment, company_b_attachment])


@pytest.fixture
def auth_headers() -> Callable[[User], dict[str, str]]:
    """Build an Authorization header for a given (unsaved) fixture user."""

    def _make(user: User) -> dict[str, str]:
        token = create_access_token(subject=user.id)
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def client(
    user_repository: FakeUserRepository,
    role_repository: FakeRoleRepository,
    company_repository: FakeCompanyRepository,
    department_repository: FakeDepartmentRepository,
    priority_repository: FakePriorityRepository,
    location_repository: FakeLocationRepository,
    category_repository: FakeCategoryRepository,
    inventory_category_repository: FakeInventoryCategoryRepository,
    inventory_item_repository: FakeInventoryItemRepository,
    inventory_transaction_repository: FakeInventoryTransactionRepository,
    ticket_repository: FakeTicketRepository,
    ticket_inventory_usage_repository: FakeTicketInventoryUsageRepository,
    comment_repository: FakeCommentRepository,
    history_repository: FakeHistoryRepository,
    attachment_repository: FakeAttachmentRepository,
    storage_service: FakeStorageService,
) -> Iterator[TestClient]:
    # The dependency-override functions below each take their own
    # `company_id: int = Depends(get_current_company_id)`, resolved fresh
    # per request off whichever fixture user's JWT the request carries -
    # exactly like the real get_x_service dependency factories in
    # app/dependencies/*.py. They mutate the *shared* fake repositories'
    # `.company_id` attribute immediately before constructing/returning a
    # service, which is safe because TestClient issues one request at a
    # time (synchronously) within a test - there is never a second request
    # in flight that could observe a different company's stale scoping.
    #
    # UserRepository is the sole exception: `get_user_repository` (used by
    # get_current_user/AuthService for identity resolution) must stay
    # permanently unscoped, so the user-management path below uses a
    # `.scoped()` view over the *same* underlying storage instead of
    # mutating `user_repository.company_id` in place - mutating it would
    # corrupt the very auth lookup this fixture's own get_current_user
    # call depends on to resolve company_id in the first place.

    def _make_history_service(company_id: int) -> HistoryService:
        history_repository.company_id = company_id
        return HistoryService(
            db=FakeSession(), company_id=company_id, history_repository=history_repository
        )

    def _make_inventory_transaction_service(company_id: int) -> InventoryTransactionService:
        inventory_transaction_repository.company_id = company_id
        return InventoryTransactionService(
            db=FakeSession(),
            company_id=company_id,
            transaction_repository=inventory_transaction_repository,
        )

    def _inventory_transaction_service(
        company_id: int = Depends(get_current_company_id),
    ) -> InventoryTransactionService:
        return _make_inventory_transaction_service(company_id)

    def _category_service(company_id: int = Depends(get_current_company_id)) -> CategoryService:
        category_repository.company_id = company_id
        return CategoryService(
            db=FakeSession(), company_id=company_id, category_repository=category_repository
        )

    def _department_service(
        company_id: int = Depends(get_current_company_id),
    ) -> DepartmentService:
        department_repository.company_id = company_id
        return DepartmentService(
            db=FakeSession(), company_id=company_id, department_repository=department_repository
        )

    def _priority_service(company_id: int = Depends(get_current_company_id)) -> PriorityService:
        priority_repository.company_id = company_id
        return PriorityService(
            db=FakeSession(), company_id=company_id, priority_repository=priority_repository
        )

    def _location_service(company_id: int = Depends(get_current_company_id)) -> LocationService:
        location_repository.company_id = company_id
        return LocationService(
            db=FakeSession(), company_id=company_id, location_repository=location_repository
        )

    def _inventory_category_service(
        company_id: int = Depends(get_current_company_id),
    ) -> InventoryCategoryService:
        inventory_category_repository.company_id = company_id
        return InventoryCategoryService(
            db=FakeSession(),
            company_id=company_id,
            inventory_category_repository=inventory_category_repository,
        )

    def _inventory_item_service(
        company_id: int = Depends(get_current_company_id),
    ) -> InventoryItemService:
        inventory_item_repository.company_id = company_id
        inventory_category_repository.company_id = company_id
        location_repository.company_id = company_id
        return InventoryItemService(
            db=FakeSession(),
            company_id=company_id,
            item_repository=inventory_item_repository,
            category_repository=inventory_category_repository,
            location_repository=location_repository,
            user_repository=user_repository.scoped(company_id),
            inventory_transaction_service=_make_inventory_transaction_service(company_id),
        )

    def _user_service(company_id: int = Depends(get_current_company_id)) -> UserService:
        department_repository.company_id = company_id
        return UserService(
            db=FakeSession(),
            company_id=company_id,
            user_repository=user_repository.scoped(company_id),
            role_repository=role_repository,
            department_repository=department_repository,
        )

    def _company_service() -> CompanyService:
        # Registration creates a brand-new company_id at call time (there
        # is no authenticated caller to derive one from - this is the one
        # public, unauthenticated write path in the whole app) - so, unlike
        # every other override above, this mutates the shared fake
        # repositories' .company_id to whatever id CompanyService.
        # register_company assigns the new company, rather than one already
        # known from get_current_company_id. Safe for the same reason as
        # every other override here: one request in flight at a time.
        def _priority_repo(company_id: int) -> FakePriorityRepository:
            priority_repository.company_id = company_id
            return priority_repository

        def _category_repo(company_id: int) -> FakeCategoryRepository:
            category_repository.company_id = company_id
            return category_repository

        def _location_repo(company_id: int) -> FakeLocationRepository:
            location_repository.company_id = company_id
            return location_repository

        def _department_repo(company_id: int) -> FakeDepartmentRepository:
            department_repository.company_id = company_id
            return department_repository

        def _inventory_category_repo(company_id: int) -> FakeInventoryCategoryRepository:
            inventory_category_repository.company_id = company_id
            return inventory_category_repository

        return CompanyService(
            db=FakeSession(),
            company_repository=company_repository,
            role_repository=role_repository,
            storage_service=storage_service,
            user_repository_factory=lambda company_id: user_repository.scoped(company_id),
            priority_repository_factory=_priority_repo,
            category_repository_factory=_category_repo,
            location_repository_factory=_location_repo,
            department_repository_factory=_department_repo,
            inventory_category_repository_factory=_inventory_category_repo,
        )

    def _make_ticket_inventory_service(company_id: int) -> TicketInventoryService:
        ticket_inventory_usage_repository.company_id = company_id
        inventory_item_repository.company_id = company_id
        ticket_repository.company_id = company_id
        return TicketInventoryService(
            db=FakeSession(),
            company_id=company_id,
            usage_repository=ticket_inventory_usage_repository,
            item_repository=inventory_item_repository,
            ticket_repository=ticket_repository,
            inventory_transaction_service=_make_inventory_transaction_service(company_id),
            history_service=_make_history_service(company_id),
        )

    def _ticket_inventory_service(
        company_id: int = Depends(get_current_company_id),
    ) -> TicketInventoryService:
        return _make_ticket_inventory_service(company_id)

    def _ticket_service(company_id: int = Depends(get_current_company_id)) -> TicketService:
        ticket_repository.company_id = company_id
        category_repository.company_id = company_id
        priority_repository.company_id = company_id
        location_repository.company_id = company_id
        return TicketService(
            db=FakeSession(),
            company_id=company_id,
            ticket_repository=ticket_repository,
            category_repository=category_repository,
            priority_repository=priority_repository,
            location_repository=location_repository,
            user_repository=user_repository.scoped(company_id),
            history_service=_make_history_service(company_id),
            storage_service=storage_service,
            ticket_inventory_service=_make_ticket_inventory_service(company_id),
        )

    def _comment_service(company_id: int = Depends(get_current_company_id)) -> CommentService:
        comment_repository.company_id = company_id
        return CommentService(
            db=FakeSession(),
            company_id=company_id,
            comment_repository=comment_repository,
            history_service=_make_history_service(company_id),
        )

    def _history_service(company_id: int = Depends(get_current_company_id)) -> HistoryService:
        return _make_history_service(company_id)

    def _attachment_service(
        company_id: int = Depends(get_current_company_id),
    ) -> AttachmentService:
        attachment_repository.company_id = company_id
        return AttachmentService(
            db=FakeSession(),
            company_id=company_id,
            attachment_repository=attachment_repository,
            storage_service=storage_service,
            history_service=_make_history_service(company_id),
        )

    # Auth resolution stays entirely unscoped and untouched by any of the
    # per-request overrides above - login/register/get_current_user must
    # work before any company is known.
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        db=FakeSession(),
        user_repository=user_repository,
        company_repository=company_repository,
    )
    app.dependency_overrides[get_company_service] = _company_service
    app.dependency_overrides[get_category_service] = _category_service
    app.dependency_overrides[get_department_service] = _department_service
    app.dependency_overrides[get_priority_service] = _priority_service
    app.dependency_overrides[get_location_service] = _location_service
    app.dependency_overrides[get_inventory_category_service] = _inventory_category_service
    app.dependency_overrides[get_inventory_item_service] = _inventory_item_service
    app.dependency_overrides[get_inventory_transaction_service] = _inventory_transaction_service
    app.dependency_overrides[get_user_service] = _user_service
    app.dependency_overrides[get_ticket_service] = _ticket_service
    app.dependency_overrides[get_ticket_inventory_service] = _ticket_inventory_service
    app.dependency_overrides[get_comment_service] = _comment_service
    app.dependency_overrides[get_history_service] = _history_service
    app.dependency_overrides[get_attachment_service] = _attachment_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
