"""add company id scoping

Revision ID: 910978056566
Revises: e05a93267ebf
Create Date: 2026-08-06 17:24:00.000000

Adds company_id to every tenant-owned table and backfills every existing
row to the "Default Company" seeded by the previous migration
(add_companies_table). This is the migration that actually makes
multi-tenancy possible at the data level - CompanyScopedRepository (a
later, code-only change) is what makes it *enforced*; this migration is
purely additive schema + a one-time backfill, no isolation logic lives here.

Column-by-column:
  - users.company_id is nullable: every existing user is a normal company
    user and gets backfilled to the Default Company, but the column stays
    nullable going forward because the future System Administrator account
    (seeded in a later migration) is platform-level and has no company.
  - tickets/departments/categories/locations/priorities.company_id are
    backfilled to the Default Company directly, then locked NOT NULL.
  - comments/attachments/ticket_history.company_id are denormalized from
    their parent ticket (backfilled via a join to tickets, not blindly set
    to the Default Company) - this is the semantically correct derivation
    even though, at this point, every ticket belongs to the same company
    anyway.

Uniqueness that was previously platform-wide becomes per-company:
users.username, users.email, tickets.ticket_number, departments.title,
categories.name, locations.title, priorities.title. The old single-column
unique constraints on these columns were created without explicit names
when their tables were first built (SQL Server auto-generates a
non-deterministic UQ__... hash per install), so this migration looks each
one up by table+column at runtime rather than hardcoding a name that would
only be correct on this one database.

Safe for existing data: every row that exists today ends up pointing at
exactly one company (the Default Company), and no row's other columns
change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '910978056566'
down_revision: Union[str, Sequence[str], None] = 'e05a93267ebf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_COMPANY_CODE = 'DEFAULT001'

# (table, column) pairs whose existing single-column unique constraint must
# be dropped and replaced with a (company_id, column) composite constraint.
_RESCOPED_UNIQUES = [
    ('users', 'username'),
    ('users', 'email'),
    ('tickets', 'ticket_number'),
    ('departments', 'title'),
    ('categories', 'name'),
    ('locations', 'title'),
    ('priorities', 'title'),
]

_FIND_UNIQUE_CONSTRAINT_SQL = sa.text(
    """
    SELECT kc.name
    FROM sys.key_constraints kc
    JOIN sys.index_columns ic ON kc.parent_object_id = ic.object_id AND kc.unique_index_id = ic.index_id
    JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
    JOIN sys.tables t ON kc.parent_object_id = t.object_id
    WHERE t.name = :table_name AND c.name = :column_name AND kc.type = 'UQ'
    """
)


def _existing_unique_constraint_name(conn, table_name: str, column_name: str) -> str:
    """Look up a single-column unique constraint's actual name.

    Needed because these constraints were originally created inline
    (`sa.UniqueConstraint('title')` with no explicit name) - SQL Server
    assigns a random UQ__... name per install, so there is no fixed name
    to hardcode here that would work on every database this migration
    might ever run against.
    """
    row = conn.execute(
        _FIND_UNIQUE_CONSTRAINT_SQL, {"table_name": table_name, "column_name": column_name}
    ).first()
    if row is None:
        raise RuntimeError(
            f"Expected a unique constraint on {table_name}.{column_name} but found none"
        )
    return row[0]


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # Tables backfilled directly to the Default Company.
    direct_tables = ["users", "departments", "categories", "locations", "priorities"]
    for table in direct_tables:
        op.add_column(table, sa.Column("company_id", sa.Integer(), nullable=True))

    # tickets is backfilled directly too, but kept separate from the loop
    # above since comments/attachments/ticket_history need it populated
    # before they can be backfilled via a join to it.
    op.add_column("tickets", sa.Column("company_id", sa.Integer(), nullable=True))

    for table in [*direct_tables, "tickets"]:
        conn.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET company_id = (SELECT id FROM companies WHERE company_code = :code)
                """
            ),
            {"code": DEFAULT_COMPANY_CODE},
        )

    # users.company_id stays nullable (the future System Administrator has
    # none); every other direct table is locked NOT NULL now that every row
    # has a value.
    for table in ["departments", "categories", "locations", "priorities", "tickets"]:
        op.alter_column(table, "company_id", existing_type=sa.Integer(), nullable=False)

    for table in direct_tables + ["tickets"]:
        op.create_foreign_key(
            f"fk_{table}_company_id_companies", table, "companies", ["company_id"], ["id"]
        )

    # Denormalized child tables: derive company_id from the parent ticket.
    for table in ["comments", "attachments", "ticket_history"]:
        op.add_column(table, sa.Column("company_id", sa.Integer(), nullable=True))
        conn.execute(
            sa.text(
                f"""
                UPDATE child
                SET child.company_id = t.company_id
                FROM {table} child
                INNER JOIN tickets t ON t.id = child.ticket_id
                """
            )
        )
        op.alter_column(table, "company_id", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(
            f"fk_{table}_company_id_companies", table, "companies", ["company_id"], ["id"]
        )

    # Re-scope uniqueness from platform-wide to per-company.
    for table, column in _RESCOPED_UNIQUES:
        old_name = _existing_unique_constraint_name(conn, table, column)
        op.drop_constraint(old_name, table, type_="unique")
        op.create_unique_constraint(
            f"uq_{table}_company_id_{column}", table, ["company_id", column]
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()

    for table, column in _RESCOPED_UNIQUES:
        op.drop_constraint(f"uq_{table}_company_id_{column}", table, type_="unique")
        op.create_unique_constraint(f"uq_{table}_{column}", table, [column])

    for table in ["comments", "attachments", "ticket_history"]:
        op.drop_constraint(f"fk_{table}_company_id_companies", table, type_="foreignkey")
        op.drop_column(table, "company_id")

    for table in ["users", "departments", "categories", "locations", "priorities", "tickets"]:
        op.drop_constraint(f"fk_{table}_company_id_companies", table, type_="foreignkey")
        op.drop_column(table, "company_id")
