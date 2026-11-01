"""add platform company and single system administrator

Revision ID: c4e1a7d2b9f0
Revises: aa1908b341bb
Create Date: 2026-11-01 14:00:00.000000

Introduces the dedicated internal organization "ITOnIT Platform
Administration" (company_code ITONIT-SYSTEM, companies.is_platform=1) and
moves the single System Administrator into it, flagged
users.is_system_administrator=1. Two filtered unique indexes make the
invariants database-enforced, concurrent writers included:

  - uq_companies_single_platform:          at most one is_platform=1 row
  - uq_users_single_system_administrator:  at most one flagged user

Preflight - nothing is changed unless ALL of these hold, otherwise the
migration raises before any DDL runs (SQL Server DDL is transactional, so
the whole revision rolls back either way):

  1. No user that belongs to a company holds the System Administrator role.
     Such a user was promoted by mistake (the pre-fix frontend sent
     hardcoded role ids - see app.core.roles). Which role they should get
     back is a human decision, so this migration never guesses.
  2. At most one company-less user exists, and if one does, it holds the
     System Administrator role - that is the legitimate legacy platform
     account, and it is adopted (moved, never recreated): its id, password
     hash, and every reference to it stay intact.
  3. No existing company already uses the reserved code ITONIT-SYSTEM.

Run `python -m app.scripts.audit_system_administrators` first to see any
conflicts. If no company-less account exists, the platform company is still
created and `python -m app.scripts.seed_initial_data` provisions the
account later.

Downgrade moves the adopted account back to company_id NULL, deletes the
platform company, and drops the indexes and columns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e1a7d2b9f0'
down_revision: Union[str, Sequence[str], None] = 'aa1908b341bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SYSTEM_ADMINISTRATOR = "System Administrator"
_PLATFORM_COMPANY_NAME = "ITOnIT Platform Administration"
_PLATFORM_COMPANY_CODE = "ITONIT-SYSTEM"


def _preflight(conn) -> int | None:
    """Raise on any conflict; return the company-less account to adopt, if any."""
    role_id = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = :name"), {"name": _SYSTEM_ADMINISTRATOR}
    ).scalar()

    tenant_holders = conn.execute(
        sa.text(
            "SELECT id FROM users WHERE role_id = :role_id AND company_id IS NOT NULL ORDER BY id"
        ),
        {"role_id": role_id},
    ).scalars().all()
    if tenant_holders:
        raise RuntimeError(
            f"Users {list(tenant_holders)} belong to a company but hold the "
            f"'{_SYSTEM_ADMINISTRATOR}' role. Reassign them to the correct company role "
            "before running this migration (see app.scripts.audit_system_administrators)."
        )

    companyless = conn.execute(
        sa.text("SELECT id, role_id FROM users WHERE company_id IS NULL ORDER BY id")
    ).all()
    if len(companyless) > 1:
        raise RuntimeError(
            f"Multiple company-less users {[u.id for u in companyless]} - expected at most one "
            "legacy System Administrator. Resolve manually before running this migration."
        )
    if companyless and companyless[0].role_id != role_id:
        raise RuntimeError(
            f"Company-less user {companyless[0].id} does not hold the "
            f"'{_SYSTEM_ADMINISTRATOR}' role. Resolve manually before running this migration."
        )

    reserved = conn.execute(
        sa.text("SELECT id FROM companies WHERE LOWER(company_code) = LOWER(:code)"),
        {"code": _PLATFORM_COMPANY_CODE},
    ).scalar()
    if reserved is not None:
        raise RuntimeError(
            f"Company {reserved} already uses the reserved code '{_PLATFORM_COMPANY_CODE}'. "
            "Rename it before running this migration."
        )

    return companyless[0].id if companyless else None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    adopt_user_id = _preflight(conn)

    op.add_column(
        "companies",
        sa.Column("is_platform", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_system_administrator", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.create_index(
        "uq_companies_single_platform",
        "companies",
        ["is_platform"],
        unique=True,
        mssql_where=sa.text("is_platform = 1"),
    )
    op.create_index(
        "uq_users_single_system_administrator",
        "users",
        ["is_system_administrator"],
        unique=True,
        mssql_where=sa.text("is_system_administrator = 1"),
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO companies (name, company_code, is_active, is_platform, timezone, language)
            VALUES (:name, :code, 1, 1, 'UTC', 'en')
            """
        ),
        {"name": _PLATFORM_COMPANY_NAME, "code": _PLATFORM_COMPANY_CODE},
    )
    if adopt_user_id is not None:
        conn.execute(
            sa.text(
                """
                UPDATE users
                SET company_id = (SELECT id FROM companies WHERE is_platform = 1),
                    is_system_administrator = 1
                WHERE id = :user_id
                """
            ),
            {"user_id": adopt_user_id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE users SET company_id = NULL
            WHERE is_system_administrator = 1
              AND company_id = (SELECT id FROM companies WHERE is_platform = 1)
            """
        )
    )
    conn.execute(sa.text("DELETE FROM companies WHERE is_platform = 1"))

    op.drop_index("uq_users_single_system_administrator", table_name="users")
    op.drop_index("uq_companies_single_platform", table_name="companies")
    op.drop_column("users", "is_system_administrator", mssql_drop_default=True)
    op.drop_column("companies", "is_platform", mssql_drop_default=True)
