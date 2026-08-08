from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.category import Category
from app.models.company import Company
from app.models.department import Department
from app.models.location import Location
from app.models.priority import Priority
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.repositories.company import CompanyRepository
from app.repositories.department import DepartmentRepository
from app.repositories.location import LocationRepository
from app.repositories.priority import PriorityRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.schemas.company import CompanyRegisterRequest

# The one role every self-registered company's first user is created with -
# never client-selectable (CompanyRegisterRequest has no role_id field at
# all). Every other user in the company - Employee, Technician, or an
# additional Company Administrator - is provisioned afterward via POST
# /users, by a Company Administrator this method creates.
_COMPANY_ADMIN_ROLE_NAME = "Company Administrator"

# Same starter values app/scripts/seed_initial_data.py uses for the
# platform's original Default Company - every newly registered company gets
# its own copy, immediately editable by its own Company Administrator
# afterward (these are company data, not shared platform constants - see
# the Priority/Category/Location/Department models' own docstrings).
_STARTER_PRIORITY_TITLES = ["Low", "Medium", "High", "Critical"]
_STARTER_CATEGORY_NAMES = ["Hardware", "Software", "Network", "Account Access", "Other"]
_STARTER_LOCATION_TITLE = "Head Office"
_STARTER_DEPARTMENT_TITLE = "General"

# Inventory categories are part of the same planned starter-data set (see
# the Company/SaaS architecture plan's Milestone 5 section), but the
# inventory_categories table doesn't exist yet - it arrives with Milestone
# 10 (Inventory core). Seeding it prematurely here would mean building
# throwaway inventory models ahead of schedule; deferred, see
# docs/TECH_DEBT.md.


class CompanyCodeConflictError(Exception):
    """Raised when a company_code is already taken, platform-wide (company
    codes are the one thing in this system that must be globally unique,
    not merely unique per company - see Company.company_code)."""


class CompanyService:
    """Owns company self-registration: creates the company, its first
    Company Administrator, and starter company data, all in one
    transaction - see register_company.

    Every repository this touches (other than company_repository/
    role_repository) is scoped to the *new* company's id, which doesn't
    exist until partway through register_company - so, unlike every other
    service in this codebase, they can't be constructed once, up front, at
    DI time. Each is instead built from a factory called with that id once
    it's known. In production the factories default to constructing the
    real repository classes (exactly what register_company would do
    inline, e.g. ``PriorityRepository(db, company_id)``); tests substitute
    factories that return their in-memory fakes instead.
    """

    def __init__(
        self,
        db: Session,
        company_repository: CompanyRepository | None = None,
        role_repository: RoleRepository | None = None,
        user_repository_factory: Callable[[int], UserRepository] | None = None,
        priority_repository_factory: Callable[[int], PriorityRepository] | None = None,
        category_repository_factory: Callable[[int], CategoryRepository] | None = None,
        location_repository_factory: Callable[[int], LocationRepository] | None = None,
        department_repository_factory: Callable[[int], DepartmentRepository] | None = None,
    ) -> None:
        self._db = db
        self._company_repository = company_repository or CompanyRepository(db)
        self._role_repository = role_repository or RoleRepository(db)
        self._user_repository_factory = user_repository_factory or (
            lambda company_id: UserRepository(db, company_id)
        )
        self._priority_repository_factory = priority_repository_factory or (
            lambda company_id: PriorityRepository(db, company_id)
        )
        self._category_repository_factory = category_repository_factory or (
            lambda company_id: CategoryRepository(db, company_id)
        )
        self._location_repository_factory = location_repository_factory or (
            lambda company_id: LocationRepository(db, company_id)
        )
        self._department_repository_factory = department_repository_factory or (
            lambda company_id: DepartmentRepository(db, company_id)
        )

    def register_company(self, payload: CompanyRegisterRequest) -> User:
        """Create a new company, its first Company Administrator, and
        starter company data, all in one transaction - nothing is
        committed until every step succeeds; any failure rolls back the
        entire thing, leaving no partially-created company behind.

        Username/email uniqueness is not checked here: both are only
        unique *within* a company (UNIQUE(company_id, username/email)), and
        a brand new company starts with zero users, so nothing this method
        creates can conflict with anything already in it. company_code is
        the one value checked, since it must be unique platform-wide.

        Returns the newly created Company Administrator (already
        committed); the route issues tokens for it via
        AuthService.issue_tokens, immediately signing them in.
        """
        if self._company_repository.get_by_code(payload.company_code) is not None:
            raise CompanyCodeConflictError

        role = self._role_repository.get_by_name(_COMPANY_ADMIN_ROLE_NAME)
        if role is None:
            # Seeded roles are a deployment invariant, not user input - a
            # missing Company Administrator role means the database was
            # never seeded.
            raise RuntimeError(f"Role '{_COMPANY_ADMIN_ROLE_NAME}' is not seeded")

        company = Company(
            name=payload.company_name,
            company_code=payload.company_code,
            theme="light",
            timezone="UTC",
            language="en",
            is_active=True,
        )

        try:
            self._company_repository.create(company)

            admin = User(
                company_id=company.id,
                username=payload.username,
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=payload.email,
                password_hash=hash_password(payload.password),
                role_id=role.id,
                is_active=True,
            )
            admin.role = role
            # get_current_active_user checks current_user.company.is_active
            # on every request - set explicitly rather than left to a lazy
            # load, since the very next request this admin makes (the
            # tokens this method's caller issues) needs it populated
            # immediately, without depending on relationship-loading
            # behavior this object happens not to have triggered yet.
            admin.company = company
            self._user_repository_factory(company.id).create(admin)

            self._seed_defaults(company.id)

            self._db.commit()
        except IntegrityError as exc:
            # Defense in depth: a concurrent request could pass the
            # company_code check above and lose the race to the database's
            # own unique constraint - the only unique constraint anything
            # in this method can actually hit (see the docstring above on
            # why username/email can't conflict for a brand new company).
            self._db.rollback()
            raise CompanyCodeConflictError from exc

        return admin

    def _seed_defaults(self, company_id: int) -> None:
        priority_repository = self._priority_repository_factory(company_id)
        for title in _STARTER_PRIORITY_TITLES:
            priority_repository.create(Priority(company_id=company_id, title=title))

        category_repository = self._category_repository_factory(company_id)
        for name in _STARTER_CATEGORY_NAMES:
            category_repository.create(
                Category(company_id=company_id, name=name, is_active=True)
            )

        self._location_repository_factory(company_id).create(
            Location(company_id=company_id, title=_STARTER_LOCATION_TITLE, is_active=True)
        )

        self._department_repository_factory(company_id).create(
            Department(company_id=company_id, title=_STARTER_DEPARTMENT_TITLE)
        )
