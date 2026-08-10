"""backfill inventory categories for existing companies

Revision ID: 5aeede95b6be
Revises: 6f69bd78f398
Create Date: 2026-08-10 11:54:21.427757

Data-only migration. CompanyService._seed_defaults only seeds starter
inventory categories for companies registered *after* this phase landed -
every company that already existed has zero inventory_categories rows and
would otherwise never get the starter list at all.

Idempotent by construction: for each company, the eleven starter names are
only inserted `WHERE NOT EXISTS` any inventory_categories row for that
company already. A company seeded by CompanyService (one row per starter
name, inserted the moment it registers) is therefore left untouched by this
migration; a company with zero rows gets exactly the eleven inserted. Running
this migration a second time is a no-op (every company now has at least one
row). Safe against a completely empty, fresh database too - zero companies
means the join produces zero candidate rows to insert.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5aeede95b6be'
down_revision: Union[str, Sequence[str], None] = '6f69bd78f398'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STARTER_INVENTORY_CATEGORY_NAMES = [
    "Laptop",
    "Desktop",
    "Monitor",
    "Printer",
    "Keyboard",
    "Mouse",
    "Dock",
    "Phone",
    "Network Equipment",
    "Cable",
    "Other",
]


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    names_values_sql = ", ".join(f"('{name}')" for name in _STARTER_INVENTORY_CATEGORY_NAMES)

    conn.execute(
        sa.text(
            f"""
            INSERT INTO inventory_categories (company_id, name, is_active, created_at)
            SELECT c.id, v.name, 1, CURRENT_TIMESTAMP
            FROM companies c
            CROSS JOIN (VALUES {names_values_sql}) AS v(name)
            WHERE NOT EXISTS (
                SELECT 1 FROM inventory_categories ic WHERE ic.company_id = c.id
            )
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema.

    Best-effort: removes rows matching the starter names inserted above.
    Cannot distinguish a backfilled row from a company administrator's own
    custom category that happens to share the same name - same limitation
    any name-based reversal of seeded data has in this codebase.
    """
    conn = op.get_bind()
    names_sql = ", ".join(f"'{name}'" for name in _STARTER_INVENTORY_CATEGORY_NAMES)
    conn.execute(sa.text(f"DELETE FROM inventory_categories WHERE name IN ({names_sql})"))
