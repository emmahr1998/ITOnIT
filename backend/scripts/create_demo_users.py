"""Development-only script: create demo users for manual testing via Swagger.

There is no public registration endpoint (by design), so this exists purely
to let a developer create a user in each role without one. It lives outside
the `app` package on purpose - it is a dev tool, not part of the deployable
application - and reuses the same building blocks as
app.scripts.seed_initial_data (UserRepository, RoleRepository, hash_password,
SessionLocal, the Default Company lookup) rather than talking to the
database directly.

Run from the backend/ directory:
    python scripts/create_demo_users.py

Idempotent: a user already present (matched by username or email) is left
untouched and reported as skipped; running this script repeatedly never
creates duplicates or overwrites an existing password. Requires the
Employee/Technician/Company Administrator roles and the Default Company to
already exist - run `python -m app.scripts.seed_initial_data` first if they
don't.

Multi-tenant note: every demo user is created on the Default Company
(company_code DEFAULT001, the same row app.scripts.seed_initial_data
resolves) - there is no unscoped/company-less user creation path here.
"""

import sys
from pathlib import Path

# This script is not part of the `app` package (see module docstring), so
# make `app` importable when run directly as `python scripts/create_demo_users.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.role import RoleRepository  # noqa: E402
from app.repositories.user import UserRepository  # noqa: E402
from app.scripts.seed_initial_data import DEFAULT_COMPANY_CODE  # noqa: E402

# (username, email, password, first_name, last_name, role_name)
# Two Company Administrator accounts on purpose - Company Administrator is
# not a singular role (any number may exist per company, all with
# identical permissions), and two distinct demo accounts exercise that.
DEMO_USERS = [
    ("admin", "admin@itonit.local", "Admin123!", "Demo", "Admin", "Company Administrator"),
    ("employee", "employee@itonit.local", "Employee123!", "Demo", "Employee", "Employee"),
    ("technician", "technician@itonit.local", "Technician123!", "Demo", "Technician", "Technician"),
    ("admin2", "admin2@itonit.local", "Admin2Pass123!", "Demo", "Admin2", "Company Administrator"),
]


def main() -> None:
    db = SessionLocal()
    try:
        company = db.scalar(select(Company).where(Company.company_code == DEFAULT_COMPANY_CODE))
        if company is None:
            raise RuntimeError(
                f"Cannot create demo users: no company with company_code "
                f"'{DEFAULT_COMPANY_CODE}' was found. Run `alembic upgrade head` "
                "and `python -m app.scripts.seed_initial_data` first."
            )

        user_repository = UserRepository(db, company.id)
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
                    company_id=company.id,
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
