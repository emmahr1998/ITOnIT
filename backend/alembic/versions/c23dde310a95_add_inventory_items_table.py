"""add inventory items table

Revision ID: c23dde310a95
Revises: 5aeede95b6be
Create Date: 2026-08-10 11:55:17.091069

Creates inventory_items - see app/models/inventory_item.py's docstring and
the approved Inventory ERD (Rev. 3) for the full design rationale. Summary
of what this migration builds:

- Three new enums as VARCHAR + CHECK columns (native_enum=False,
  create_constraint=True - same convention as tickets.status):
  tracking_type, status, condition (condition is nullable).
- Two FKs get a real database-level ON DELETE SET NULL:
  current_location_id -> locations.id, current_holder_user_id -> users.id.
  Every other FK here (company_id, inventory_category_id) is NO ACTION -
  no new DB-level CASCADE path is introduced, consistent with every other
  tenant-owned table in this schema.
- A filtered unique index on (company_id, asset_tag), WHERE asset_tag IS
  NOT NULL - not a plain UNIQUE constraint, since SQL Server's plain UNIQUE
  treats NULL as a comparable value and would incorrectly cap a company at
  one untagged BULK item.
- Eight CHECK constraints enforcing the SERIALIZED vs. BULK rules from the
  approved ERD, §05 (exact list in each constraint's name below).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c23dde310a95'
down_revision: Union[str, Sequence[str], None] = '5aeede95b6be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'inventory_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('inventory_category_id', sa.Integer(), nullable=False),
        sa.Column('current_location_id', sa.Integer(), nullable=True),
        sa.Column('current_holder_user_id', sa.Integer(), nullable=True),
        sa.Column('asset_tag', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('manufacturer', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column(
            'tracking_type',
            sa.Enum(
                'SERIALIZED', 'BULK',
                name='ck_inventory_items_tracking_type', native_enum=False,
                create_constraint=True, length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.Enum(
                'AVAILABLE', 'RESERVED', 'IN_USE', 'IN_REPAIR', 'RETIRED',
                name='ck_inventory_items_status', native_enum=False,
                create_constraint=True, length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            'condition',
            sa.Enum(
                'NEW', 'GOOD', 'FAIR', 'DAMAGED', 'BROKEN',
                name='ck_inventory_items_condition', native_enum=False,
                create_constraint=True, length=20,
            ),
            nullable=True,
        ),
        sa.Column('stock_quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('reserved_quantity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('minimum_stock', sa.Integer(), nullable=True),
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('warranty_expiration', sa.Date(), nullable=True),
        sa.Column('supplier', sa.String(length=150), nullable=True),
        sa.Column('purchase_cost', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('invoice_number', sa.String(length=100), nullable=True),
        sa.Column('image_path', sa.String(length=500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['inventory_category_id'], ['inventory_categories.id'], ),
        sa.ForeignKeyConstraint(['current_location_id'], ['locations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['current_holder_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        'ux_inventory_items_company_id_asset_tag',
        'inventory_items',
        ['company_id', 'asset_tag'],
        unique=True,
        mssql_where=sa.text('asset_tag IS NOT NULL'),
    )

    op.create_check_constraint(
        'ck_inventory_items_serialized_asset_tag',
        'inventory_items',
        "tracking_type <> 'SERIALIZED' OR asset_tag IS NOT NULL",
    )
    op.create_check_constraint(
        'ck_inventory_items_serialized_stock_one',
        'inventory_items',
        "tracking_type <> 'SERIALIZED' OR stock_quantity = 1",
    )
    op.create_check_constraint(
        'ck_inventory_items_serialized_reserved_bound',
        'inventory_items',
        "tracking_type <> 'SERIALIZED' OR reserved_quantity IN (0, 1)",
    )
    op.create_check_constraint(
        'ck_inventory_items_bulk_status',
        'inventory_items',
        "tracking_type <> 'BULK' OR status IN ('AVAILABLE', 'RETIRED')",
    )
    op.create_check_constraint(
        'ck_inventory_items_bulk_no_holder',
        'inventory_items',
        "tracking_type <> 'BULK' OR current_holder_user_id IS NULL",
    )
    op.create_check_constraint(
        'ck_inventory_items_stock_nonneg', 'inventory_items', 'stock_quantity >= 0'
    )
    op.create_check_constraint(
        'ck_inventory_items_reserved_nonneg', 'inventory_items', 'reserved_quantity >= 0'
    )
    op.create_check_constraint(
        'ck_inventory_items_reserved_le_stock',
        'inventory_items',
        'reserved_quantity <= stock_quantity',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('inventory_items')
