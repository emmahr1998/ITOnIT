"""add ticket inventory usage table

Revision ID: 8c2704833d20
Revises: c23dde310a95
Create Date: 2026-08-10 21:05:29.183370

Creates ticket_inventory_usage - see app/models/ticket_inventory_usage.py's
docstring and the approved Inventory ERD (Rev. 3) for the full design
rationale. Summary of what this migration builds:

- One new enum as a VARCHAR + CHECK column (native_enum=False,
  create_constraint=True - same convention as tickets.status/
  inventory_items.status): status (RESERVED/CONSUMED).
- Every FK here is NO ACTION (no server_default ON DELETE action) except
  none needed SET NULL - consistent with every other tenant-owned table in
  this schema; app-layer teardown (TicketService.delete_ticket /
  TicketInventoryService.release_all_for_ticket) reverts the referenced
  InventoryItem's state before removing rows here, rather than relying on
  a DB-level cascade to do it silently.
- A unique constraint on (ticket_id, inventory_item_id): at most one
  "current" usage row may exist per ticket+item pair at a time - a second
  BULK reservation of an already-attached item merges into the existing
  row's quantity instead (see TicketInventoryService.reserve).
- A CHECK constraint enforcing quantity > 0.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c2704833d20'
down_revision: Union[str, Sequence[str], None] = 'c23dde310a95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ticket_inventory_usage',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'RESERVED', 'CONSUMED',
                name='ck_ticket_inventory_usage_status', native_enum=False,
                create_constraint=True, length=20,
            ),
            nullable=False,
        ),
        sa.Column('selected_by_user_id', sa.Integer(), nullable=False),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.CheckConstraint('quantity > 0', name='ck_ticket_inventory_usage_quantity_positive'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id'], ),
        sa.ForeignKeyConstraint(['selected_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'ticket_id', 'inventory_item_id', name='uq_ticket_inventory_usage_ticket_item'
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ticket_inventory_usage')
