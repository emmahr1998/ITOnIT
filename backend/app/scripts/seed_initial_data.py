"""Idempotent bootstrap script: seed roles, the Default Company's priorities,
and an optional initial admin user.

Run with:
    python -m app.scripts.seed_initial_data

Safe to run repeatedly - existing roles, priorities, and the admin user
(matched by email) are left untouched. Not run automatically on
application startup.

Multi-tenant note: priorities and the optional admin user are seeded onto
the "Default Company" row created by the add_companies_table migration
(company_code DEFAULT001), resolved by that code rather than assuming a
hardcoded id - this is the same lookup pattern the add_company_id_scoping
migration itself uses when backfilling pre-existing rows. This script does
not create companies; it only seeds the one starting company/tenant a
fresh install already has from migrations. Real per-company registration
(and the seeding that comes with it) is a later milestone.

Atomicity: one commit at the end, one rollback on any exception - either
every step below succeeds or none of it is persisted. This is deliberate:
a partially-seeded database (e.g. roles but no priorities) is arguably
worse than an unseeded one, since it looks bootstrapped but isn't.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.company import Company
from app.models.priority import Priority
from app.models.role import Role
from app.models.user import User
from app.repositories.priority import PriorityRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository

# Per docs/database-design.md section 3 ("Roles Table" initial records).
# System Administrator is seeded here as a role only - no user is created
# for it (see the role-consolidation migration's docstring for why); the
# account and its /platform/* routes arrive with the Platform Admin Console
# milestone.
ROLE_NAMES = ["Employee", "Technician", "Company Administrator", "System Administrator"]
ADMIN_ROLE_NAME = "Company Administrator"

# Same default priorities the priorities-table migration seeds - listed
# again here so a fresh/rolled-back database is still left in a usable
# state by this script alone.
PRIORITY_TITLES = ["Low", "Medium", "High", "Critical"]

# The Default Company seeded by the add_companies_table migration - see
# that migration's DEFAULT_COMPANY_CODE for the source of truth this
# mirrors. Every row this script creates below belongs to it.
DEFAULT_COMPANY_CODE = "DEFAULT001"


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


def main() -> None:
    db = SessionLocal()
    try:
        _seed_roles(RoleRepository(db))
        company = _get_default_company(db)
        _seed_priorities(PriorityRepository(db, company.id), company.id)
        _seed_admin_user(UserRepository(db, company.id), RoleRepository(db), company.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
