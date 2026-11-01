"""Idempotent bootstrap script: seed roles, the Default Company's priorities,
an optional initial admin user, the dedicated platform company, and an
optional platform-level System Administrator account.

Run with:
    python -m app.scripts.seed_initial_data

Safe to run repeatedly - existing roles, priorities, the admin user
(matched by email), the platform company, and the System Administrator are
left untouched. Not run automatically on application startup.

Multi-tenant note: priorities and the optional admin user are seeded onto
the "Default Company" row created by the add_companies_table migration
(company_code DEFAULT001), resolved by that code rather than assuming a
hardcoded id - this is the same lookup pattern the add_company_id_scoping
migration itself uses when backfilling pre-existing rows. Additional
customer companies are created through registration (POST
/companies/register) or, by a System Administrator, POST /platform/companies -
each seeds its own starter data.

Platform bootstrap is the ONLY way the System Administrator account is ever
created - there is no API route for it, and user management can never assign
that role. It refuses to run (and changes nothing) if any user other than the
single flagged account already holds the System Administrator role: that is
conflicting data a person must resolve first, never something this script
silently "fixes". The database's own filtered unique indexes
(uq_companies_single_platform, uq_users_single_system_administrator) are the
final guarantee against concurrent runs creating a duplicate.

Atomicity: one commit at the end, one rollback on any exception - either
every step below succeeds or none of it is persisted. This is deliberate:
a partially-seeded database (e.g. roles but no priorities) is arguably
worse than an unseeded one, since it looks bootstrapped but isn't.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.roles import (
    COMPANY_ADMINISTRATOR_ROLE,
    COMPANY_ROLE_NAMES,
    PLATFORM_COMPANY_CODE,
    PLATFORM_COMPANY_NAME,
    SYSTEM_ADMINISTRATOR_ROLE,
)
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.company import Company
from app.models.priority import Priority
from app.models.role import Role
from app.models.user import User
from app.repositories.company import CompanyRepository
from app.repositories.priority import PriorityRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository

# Per docs/database-design.md section 3 ("Roles Table" initial records).
# System Administrator is always seeded as a role; its one platform-level
# user is seeded separately, conditionally, by _seed_platform_administrator
# below - see that function's own docstring.
ROLE_NAMES = [*COMPANY_ROLE_NAMES, SYSTEM_ADMINISTRATOR_ROLE]
ADMIN_ROLE_NAME = COMPANY_ADMINISTRATOR_ROLE
PLATFORM_ADMIN_ROLE_NAME = SYSTEM_ADMINISTRATOR_ROLE

# Same default priorities the priorities-table migration seeds - listed
# again here so a fresh/rolled-back database is still left in a usable
# state by this script alone.
PRIORITY_TITLES = ["Low", "Medium", "High", "Critical"]

# The Default Company seeded by the add_companies_table migration - see
# that migration's DEFAULT_COMPANY_CODE for the source of truth this
# mirrors. Priorities and the initial admin user belong to it.
DEFAULT_COMPANY_CODE = "DEFAULT001"


class PlatformBootstrapConflictError(RuntimeError):
    """Existing data contradicts the single-System-Administrator invariant.
    Nothing is changed; the message says what must be resolved by hand."""


def _seed_roles(role_repository: RoleRepository) -> None:
    for name in ROLE_NAMES:
        if role_repository.get_by_name(name) is None:
            role_repository.create(Role(name=name))
            print(f"Created role: {name}")
        else:
            print(f"Role already exists, skipped: {name}")


def _get_default_company(db: Session) -> Company:
    company = db.scalar(select(Company).where(Company.company_code == DEFAULT_COMPANY_CODE))
    if company is None:
        raise RuntimeError(
            f"Cannot seed priorities/admin user: no company with company_code "
            f"'{DEFAULT_COMPANY_CODE}' was found. Run `alembic upgrade head` "
            "first - the add_companies_table migration creates this row."
        )
    return company


def _seed_priorities(priority_repository: PriorityRepository, company_id: int) -> None:
    for title in PRIORITY_TITLES:
        if priority_repository.get_by_title(title) is None:
            priority_repository.create(Priority(company_id=company_id, title=title))
            print(f"Created priority: {title}")
        else:
            print(f"Priority already exists, skipped: {title}")


def _seed_admin_user(
    user_repository: UserRepository, role_repository: RoleRepository, company_id: int
) -> None:
    if not settings.INITIAL_ADMIN_EMAIL or not settings.INITIAL_ADMIN_PASSWORD:
        print(
            "Skipping admin user creation: "
            "INITIAL_ADMIN_EMAIL / INITIAL_ADMIN_PASSWORD not set."
        )
        return

    if user_repository.get_by_email(settings.INITIAL_ADMIN_EMAIL) is not None:
        print(f"Admin user already exists, skipped: {settings.INITIAL_ADMIN_EMAIL}")
        return

    admin_role = role_repository.get_by_name(ADMIN_ROLE_NAME)
    if admin_role is None:
        raise RuntimeError(f"Cannot seed admin user: '{ADMIN_ROLE_NAME}' role was not found.")

    username = settings.INITIAL_ADMIN_EMAIL.split("@")[0]
    user_repository.create(
        User(
            company_id=company_id,
            username=username,
            email=settings.INITIAL_ADMIN_EMAIL,
            password_hash=hash_password(settings.INITIAL_ADMIN_PASSWORD),
            first_name=settings.INITIAL_ADMIN_FIRST_NAME or "Admin",
            last_name=settings.INITIAL_ADMIN_LAST_NAME or "User",
            role_id=admin_role.id,
            is_active=True,
        )
    )
    print(f"Created admin user: {settings.INITIAL_ADMIN_EMAIL} (username: {username})")


def _seed_platform_company(company_repository: CompanyRepository) -> Company:
    """Return the single platform company, creating it on first run.

    Never creates a second one (uq_companies_single_platform would reject
    it anyway), and never adopts a customer company that happens to use the
    reserved code - that is a conflict to resolve by hand.
    """
    existing = company_repository.get_platform_company()
    if existing is not None:
        print(f"Platform company already exists, skipped: {existing.company_code}")
        return existing

    if company_repository.get_by_code(PLATFORM_COMPANY_CODE) is not None:
        raise PlatformBootstrapConflictError(
            f"A customer company already uses the reserved code '{PLATFORM_COMPANY_CODE}'. "
            "Rename it before bootstrapping the platform company."
        )

    company = company_repository.create(
        Company(
            name=PLATFORM_COMPANY_NAME,
            company_code=PLATFORM_COMPANY_CODE,
            is_active=True,
            is_platform=True,
        )
    )
    print(f"Created platform company: {PLATFORM_COMPANY_NAME} ({PLATFORM_COMPANY_CODE})")
    return company


def _seed_platform_administrator(
    user_repository: UserRepository, role_repository: RoleRepository, platform_company: Company
) -> None:
    """Bootstraps the single platform-level System Administrator account,
    in the platform company, flagged is_system_administrator.

    Idempotent by "does a flagged account exist at all", not by email: if
    one exists it is left untouched even when PLATFORM_ADMIN_EMAIL now
    names someone else - the bootstrap never creates a second account or
    reassigns the existing one. ``user_repository`` must be unscoped
    (UserRepository(db)).
    """
    platform_role = role_repository.get_by_name(PLATFORM_ADMIN_ROLE_NAME)
    if platform_role is None:
        raise RuntimeError(
            f"Cannot seed platform administrator: '{PLATFORM_ADMIN_ROLE_NAME}' role was not found."
        )

    # Anyone holding the role without being the flagged platform account is
    # either a tenant user promoted by mistake or a legacy company-less row
    # the add_platform_company migration has not adopted yet. Either way a
    # person must decide - refuse rather than guess.
    unexpected = [
        u
        for u in user_repository.list_by_role_id_unscoped(platform_role.id)
        if not (u.is_system_administrator and u.company_id == platform_company.id)
    ]
    if unexpected:
        ids = ", ".join(str(u.id) for u in sorted(unexpected, key=lambda u: u.id))
        raise PlatformBootstrapConflictError(
            f"Users {ids} hold the '{PLATFORM_ADMIN_ROLE_NAME}' role but are not the "
            "platform account. Resolve them before bootstrapping (see "
            "python -m app.scripts.audit_system_administrators)."
        )

    if user_repository.get_system_administrator() is not None:
        print("Platform administrator already exists, skipped.")
        return

    if not settings.PLATFORM_ADMIN_EMAIL or not settings.PLATFORM_ADMIN_PASSWORD:
        print(
            "Skipping platform administrator creation: "
            "PLATFORM_ADMIN_EMAIL / PLATFORM_ADMIN_PASSWORD not set."
        )
        return

    username = settings.PLATFORM_ADMIN_EMAIL.split("@")[0]
    try:
        user_repository.create(
            User(
                company_id=platform_company.id,
                username=username,
                email=settings.PLATFORM_ADMIN_EMAIL,
                password_hash=hash_password(settings.PLATFORM_ADMIN_PASSWORD),
                first_name=settings.PLATFORM_ADMIN_FIRST_NAME or "Platform",
                last_name=settings.PLATFORM_ADMIN_LAST_NAME or "Administrator",
                role_id=platform_role.id,
                is_active=True,
                is_system_administrator=True,
            )
        )
    except IntegrityError as exc:
        # uq_users_single_system_administrator: a concurrent run won.
        raise PlatformBootstrapConflictError(
            "Another process created the platform administrator concurrently."
        ) from exc
    print(f"Created platform administrator (username: {username})")


def main() -> None:
    db = SessionLocal()
    try:
        _seed_roles(RoleRepository(db))
        company = _get_default_company(db)
        _seed_priorities(PriorityRepository(db, company.id), company.id)
        _seed_admin_user(UserRepository(db, company.id), RoleRepository(db), company.id)
        platform_company = _seed_platform_company(CompanyRepository(db))
        _seed_platform_administrator(UserRepository(db), RoleRepository(db), platform_company)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
