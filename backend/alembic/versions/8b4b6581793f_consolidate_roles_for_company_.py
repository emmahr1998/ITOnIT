"""consolidate roles for company administrator

Revision ID: 8b4b6581793f
Revises: 910978056566
Create Date: 2026-08-06 20:09:39.124877

Role consolidation: the four roles become Employee, Technician, Company
Administrator, System Administrator - Manager is retired and merged into
Company Administrator. This is a pure *data* migration - the roles table's
shape (id, name, description) does not change, only its rows do, so there
is no add_column/alter_column here at all.

Order of operations matters:
  1. Rename Administrator -> Company Administrator in place (UPDATE, not a
     new row), so every existing users.role_id FK pointing at it keeps
     working with zero row-by-row user changes.
  2. Reassign every user currently on Manager to the (now-renamed) Company
     Administrator role. Manager had strictly fewer permissions than
     Administrator in every case (could not manage locations, create
     users, set another user's password, or fully edit another user's
     admin fields - see backend/app/services/user_service.py and
     backend/app/api/routes/locations.py|users.py) - this is an
     intentional, one-directional privilege increase for former Managers,
     not a lossless reshuffle.
  3. Only now that no user references Manager can its role row be deleted.
  4. Seed the System Administrator role row. Deliberately role-only: no
     user is seeded for it here, and no route can reach it yet
     (get_current_company_id 403s any company_id IS NULL user on every
     existing endpoint) - seeding an actual account now would just be
     another locked-out account, like the POST /auth/register gap already
     tracked in docs/TECH_DEBT.md. The real account and its routes arrive
     together with the Platform Admin Console milestone.

Downgrade is deliberately lossy and documented as such: it recreates the
Manager role and renames Company Administrator back to Administrator, but
it cannot know which specific users were originally Manager vs.
Administrator - that distinction is destroyed by step 2 above. The only
honest downgrade is "every affected user becomes Administrator" - this is
a one-way data merge, not a reversible schema change.

Backward-compatibility note: every role-name string check in the
application (require_roles(...), the _MANAGE_ROLES-style constants in
routes/services) must be updated to the new names *atomically* with this
migration. Running this migration against code that still checks for the
literal strings "Administrator"/"Manager" would 403 every existing
Company Administrator (nee Administrator/Manager) user on every gated
route until the code catches up.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b4b6581793f'
down_revision: Union[str, Sequence[str], None] = '910978056566'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ADMINISTRATOR = "Administrator"
_COMPANY_ADMINISTRATOR = "Company Administrator"
_MANAGER = "Manager"
_SYSTEM_ADMINISTRATOR = "System Administrator"


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    conn.execute(
        sa.text("UPDATE roles SET name = :new_name WHERE name = :old_name"),
        {"new_name": _COMPANY_ADMINISTRATOR, "old_name": _ADMINISTRATOR},
    )

    conn.execute(
        sa.text(
            """
            UPDATE users
            SET role_id = (SELECT id FROM roles WHERE name = :company_admin)
            WHERE role_id = (SELECT id FROM roles WHERE name = :manager)
            """
        ),
        {"company_admin": _COMPANY_ADMINISTRATOR, "manager": _MANAGER},
    )

    conn.execute(sa.text("DELETE FROM roles WHERE name = :manager"), {"manager": _MANAGER})

    conn.execute(
        sa.text(
            "INSERT INTO roles (name, description) VALUES (:name, :description)"
        ),
        {
            "name": _SYSTEM_ADMINISTRATOR,
            "description": (
                "Platform-level role, owned by ITOnIT itself. Not yet backed by "
                "a seeded user - arrives with the Platform Admin Console milestone."
            ),
        },
    )


def downgrade() -> None:
    """Downgrade schema.

    Lossy: every user currently on Company Administrator (whether they were
    originally Administrator or Manager) becomes Administrator - the
    original Manager/Administrator split cannot be reconstructed. See the
    module docstring.
    """
    conn = op.get_bind()

    conn.execute(sa.text("DELETE FROM roles WHERE name = :name"), {"name": _SYSTEM_ADMINISTRATOR})

    conn.execute(
        sa.text("INSERT INTO roles (name, description) VALUES (:name, NULL)"),
        {"name": _MANAGER},
    )

    conn.execute(
        sa.text("UPDATE roles SET name = :old_name WHERE name = :new_name"),
        {"old_name": _ADMINISTRATOR, "new_name": _COMPANY_ADMINISTRATOR},
    )
