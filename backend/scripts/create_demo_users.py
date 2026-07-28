"""Development-only script: create demo users for manual testing via Swagger.

There is no public registration endpoint (by design), so this exists purely
to let a developer create a user in each role without one. It lives outside
the `app` package on purpose - it is a dev tool, not part of the deployable
application - and reuses the same building blocks as
app.scripts.seed_initial_data (UserRepository, RoleRepository, hash_password,
SessionLocal) rather than talking to the database directly.

Run from the backend/ directory:
    python scripts/create_demo_users.py

Idempotent: a user already present (matched by username or email) is left
untouched and reported as skipped; running this script repeatedly never
creates duplicates. Requires the Employee/Technician/Manager/Administrator
roles to already exist - run `python -m app.scripts.seed_initial_data`
first if they don't.
"""

import sys
from pathlib import Path

# This script is not part of the `app` package (see module docstring), so
# make `app` importable when run directly as `python scripts/create_demo_users.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.role import RoleRepository  # noqa: E402
from app.repositories.user import UserRepository  # noqa: E402

# (username, email, password, first_name, last_name, role_name)
DEMO_USERS = [
    ("admin", "admin@itonit.local", "Admin123!", "Demo", "Admin", "Administrator"),
    ("employee", "employee@itonit.local", "Employee123!", "Demo", "Employee", "Employee"),
    ("technician", "technician@itonit.local", "Technician123!", "Demo", "Technician", "Technician"),
    ("manager", "manager@itonit.local", "Manager123!", "Demo", "Manager", "Manager"),
]


def main() -> None:
    db = SessionLocal()
    try:
        user_repository = UserRepository(db)
        role_repository = RoleRepository(db)

        for username, email, password, first_name, last_name, role_name in DEMO_USERS:
            existing = user_repository.get_by_username(username) or user_repository.get_by_email(
                email
            )
            if existing is not None:
                print(f"Already exists, skipped: {username} ({email})")
                continue

            role = role_repository.get_by_name(role_name)
            if role is None:
                raise RuntimeError(
                    f"Cannot create {username}: '{role_name}' role was not found. "
                    "Run `python -m app.scripts.seed_initial_data` first."
                )

            user_repository.create(
                User(
                    username=username,
                    email=email,
                    password_hash=hash_password(password),
                    first_name=first_name,
                    last_name=last_name,
                    role_id=role.id,
                    is_active=True,
                )
            )
            print(f"Created: {username} / {email} ({role_name})")

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
