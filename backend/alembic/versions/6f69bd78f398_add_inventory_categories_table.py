"""add inventory categories table

Revision ID: 6f69bd78f398
Revises: 8b4b6581793f
Create Date: 2026-08-09 00:28:32.486729

Creates inventory_categories - the company-scoped lookup table that
classifies inventory items by asset type (Laptop, Monitor, Cable, ...),
mirroring the existing categories/locations/priorities pattern exactly:
CreatedAtMixin only (no updated_at - matches Category, not Location),
UNIQUE(company_id, name), is_active soft-deactivation, no ON DELETE
CASCADE on company_id (consistent with every other tenant-owned table in
this schema - see the approved Inventory ERD, §03).

Newly registered companies are seeded with the starter category list by
CompanyService._seed_defaults as of this same phase; companies registered
before this migration existed are backfilled separately by the next
migration in this chain.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f69bd78f398'
down_revision: Union[str, Sequence[str], None] = '8b4b6581793f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'inventory_categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'company_id', 'name', name='uq_inventory_categories_company_id_name'
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('inventory_categories')
