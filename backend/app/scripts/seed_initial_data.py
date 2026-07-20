"""Idempotent bootstrap script: seed roles and an optional initial admin user.

Run with:
    python -m app.scripts.seed_initial_data

Safe to run repeatedly - existing roles and the admin user (matched by
email) are left untouched. Not run automatically on application startup.
"""

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository

# Per docs/database-design.md section 3 ("Roles Table" initial records).
ROLE_NAMES = ["Employee", "Technician", "Manager", "Administrator"]
ADMIN_ROLE_NAME = "Administrator"


def _seed_roles(role_repository: RoleRepository) -> None:
    for name in ROLE_NAMES:
        if role_repository.get_by_name(name) is None:
            role_repository.create(Role(name=name))
            print(f"Created role: {name}")
        else:
            print(f"Role already exists, skipped: {name}")


def _seed_admin_user(user_repository: UserRepository, role_repository: RoleRepository) -> None:
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

    user_repository.create(
        User(
            email=settings.INITIAL_ADMIN_EMAIL,
            password_hash=hash_password(settings.INITIAL_ADMIN_PASSWORD),
            first_name=settings.INITIAL_ADMIN_FIRST_NAME or "Admin",
            last_name=settings.INITIAL_ADMIN_LAST_NAME or "User",
            role_id=admin_role.id,
            is_active=True,
        )
    )
    print(f"Created admin user: {settings.INITIAL_ADMIN_EMAIL}")


def main() -> None:
    db = SessionLocal()
    try:
        _seed_roles(RoleRepository(db))
        _seed_admin_user(UserRepository(db), RoleRepository(db))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
