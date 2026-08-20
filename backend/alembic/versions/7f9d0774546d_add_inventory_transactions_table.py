"""add inventory transactions table

Revision ID: 7f9d0774546d
Revises: 8c2704833d20
Create Date: 2026-08-12 18:51:56.087077

Creates inventory_transactions - the permanent, append-only audit trail
for InventoryItem changes (Phase 12.1). See
app/models/inventory_transaction.py's docstring and the approved
InventoryTransaction design doc for the full rationale. Summary of what
this migration builds:

- One new enum as a VARCHAR + CHECK column (native_enum=False,
  create_constraint=True - same convention as every other enum column in
  this schema): transaction_type.
- ticket_id is the one FK here with ON DELETE SET NULL rather than this
  schema's usual NO ACTION - TicketService.delete_ticket hard-deletes
  ticket rows, and a NO ACTION FK would make that delete fail once a
  transaction row references it. SET NULL lets the ticket disappear
  while the transaction row (and its human-readable ticket reference,
  preserved in `notes` for the ticket-deletion-cleanup case) survives -
  mirrors inventory_items.current_location_id/current_holder_user_id's
  existing use of SET NULL for the same reason.
- Two indexes: (company_id, inventory_item_id, created_at) for the
  per-item history query, (company_id, ticket_id) for ticket-scoped
  filtering.
- No backfill: historical Milestone 11 activity that predates this table
  has no reliable source to reconstruct from, so the table starts empty.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f9d0774546d'
down_revision: Union[str, Sequence[str], None] = '8c2704833d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'inventory_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('performed_by_user_id', sa.Integer(), nullable=False),
        sa.Column(
            'transaction_type',
            sa.Enum(
                'CREATED', 'EDITED', 'STOCK_ADJUSTED', 'STATUS_CHANGED', 'HOLDER_CHANGED',
                'LOCATION_CHANGED', 'RESERVED', 'RELEASED', 'CONSUMED', 'CONSUME_UNDONE',
                name='ck_inventory_transactions_type', native_enum=False,
                create_constraint=True, length=20,
            ),
            nullable=False,
        ),
        sa.Column('quantity_delta', sa.Integer(), nullable=True),
        sa.Column('field_name', sa.String(length=50), nullable=True),
        sa.Column('old_value', sa.String(length=255), nullable=True),
        sa.Column('new_value', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id'], ),
        sa.ForeignKeyConstraint(['performed_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_inventory_transactions_company_item_created', 'inventory_transactions',
        ['company_id', 'inventory_item_id', 'created_at'], unique=False,
    )
    op.create_index(
        'ix_inventory_transactions_company_ticket', 'inventory_transactions',
        ['company_id', 'ticket_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_inventory_transactions_company_ticket', table_name='inventory_transactions')
    op.drop_index('ix_inventory_transactions_company_item_created', table_name='inventory_transactions')
    op.drop_table('inventory_transactions')
