"""add companies table

Revision ID: e05a93267ebf
Revises: 5a79efa03786
Create Date: 2026-08-06 17:21:05.279462

Introduces the Company entity: ITOnIT is becoming a multi-tenant platform,
and every existing row (users, tickets, departments, categories, locations,
priorities, comments, attachments, ticket_history) needs to belong to
exactly one company. This migration only creates the table and seeds one
"Default Company" row to eventually own all pre-existing data - the
company_id columns/backfill/constraint changes on those other tables are
a separate migration (add_company_id_scoping) so each step stays small and
independently reviewable.

Safe for existing data: this migration creates a new table and inserts one
new row - it does not touch any existing table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e05a93267ebf'
down_revision: Union[str, Sequence[str], None] = '5a79efa03786'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# company_code of the seed "Default Company" row - the next migration
# (add_company_id_scoping) looks it up by this code (rather than assuming a
# hardcoded id) when backfilling every pre-existing row.
DEFAULT_COMPANY_CODE = 'DEFAULT001'


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('company_code', sa.String(length=20), nullable=False),
        sa.Column('logo_path', sa.String(length=500), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('theme', sa.String(length=20), nullable=False, server_default='light'),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='UTC'),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_code'),
    )

    # Seed one company to eventually own every pre-existing row. All current
    # data is dev/demo data (no production customers exist yet), so a single
    # default tenant is a safe, reversible starting point. id is left to the
    # identity column - the next migration looks this row up by
    # company_code instead of assuming a specific id.
    op.execute(
        f"""
        INSERT INTO companies (name, company_code, is_active, created_at, updated_at)
        VALUES ('Default Company', '{DEFAULT_COMPANY_CODE}', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('companies')
