"""add locations table and migrate ticket location

Revision ID: 5a79efa03786
Revises: 437e3e3195e1
Create Date: 2026-07-31 14:27:56.606981

Replaces Ticket.location (a free-text VARCHAR) with Ticket.location_id, a
nullable foreign key into a new locations table - locations are now chosen
from a predefined, admin-managed list instead of typed freely, matching
Category/Priority. Locations are deactivated (is_active=False), never
deleted, so a ticket that already references one is unaffected if it's
later retired from the selectable list.

Safe for existing data: every ticket's existing distinct, non-null free-text
location becomes a real Location row (active by default) before
location_id is backfilled by matching on title, and only then is the old
`location` column dropped. location_id stays nullable, matching the
nullability the old `location` column already had.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a79efa03786'
down_revision: Union[str, Sequence[str], None] = '437e3e3195e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'locations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('title'),
    )

    op.add_column('tickets', sa.Column('location_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_tickets_location_id_locations', 'tickets', 'locations', ['location_id'], ['id']
    )

    # Data migration: distinct existing free-text locations -> real Location rows.
    op.execute(
        """
        INSERT INTO locations (title, is_active, created_at, updated_at)
        SELECT DISTINCT location, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM tickets
        WHERE location IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE t
        SET t.location_id = l.id
        FROM tickets t
        INNER JOIN locations l ON l.title = t.location
        WHERE t.location IS NOT NULL
        """
    )

    op.drop_column('tickets', 'location')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('tickets', sa.Column('location', sa.String(length=200), nullable=True))
    op.execute(
        """
        UPDATE t
        SET t.location = l.title
        FROM tickets t
        INNER JOIN locations l ON l.id = t.location_id
        """
    )

    op.drop_constraint('fk_tickets_location_id_locations', 'tickets', type_='foreignkey')
    op.drop_column('tickets', 'location_id')

    op.drop_table('locations')
