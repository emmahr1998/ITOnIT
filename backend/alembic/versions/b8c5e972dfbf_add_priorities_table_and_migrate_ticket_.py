"""add priorities table and migrate ticket priority to fk

Revision ID: b8c5e972dfbf
Revises: 496ee3278515
Create Date: 2026-07-28 09:57:59.605993

Replaces Ticket.priority (a native_enum=False VARCHAR with a CHECK
constraint) with Ticket.priority_id, a foreign key into a new priorities
table seeded with the same four default levels. Also adds Ticket.location.

Safe for existing data: the four default Priority rows are inserted first,
every existing ticket's old enum value is mapped onto the matching Priority
row by title before priority_id is made NOT NULL, and only then is the old
column (and its ck_tickets_priority constraint) dropped.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c5e972dfbf'
down_revision: Union[str, Sequence[str], None] = '496ee3278515'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_PRIORITIES = ["Low", "Medium", "High", "Critical"]
_ENUM_TO_TITLE_CASE = """
    CASE tickets.priority
        WHEN 'LOW' THEN 'Low'
        WHEN 'MEDIUM' THEN 'Medium'
        WHEN 'HIGH' THEN 'High'
        WHEN 'CRITICAL' THEN 'Critical'
    END
"""
_TITLE_TO_ENUM_CASE = """
    CASE priorities.title
        WHEN 'Low' THEN 'LOW'
        WHEN 'Medium' THEN 'MEDIUM'
        WHEN 'High' THEN 'HIGH'
        WHEN 'Critical' THEN 'CRITICAL'
    END
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'priorities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=50), nullable=False),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('title'),
    )

    priorities_table = sa.table("priorities", sa.column("title", sa.String))
    op.bulk_insert(priorities_table, [{"title": title} for title in _DEFAULT_PRIORITIES])

    op.add_column('tickets', sa.Column('priority_id', sa.Integer(), nullable=True))
    op.add_column('tickets', sa.Column('location', sa.String(length=200), nullable=True))
    op.create_foreign_key(
        'fk_tickets_priority_id_priorities', 'tickets', 'priorities', ['priority_id'], ['id']
    )

    op.execute(
        f"""
        UPDATE tickets
        SET tickets.priority_id = priorities.id
        FROM tickets
        INNER JOIN priorities ON priorities.title = ({_ENUM_TO_TITLE_CASE})
        """
    )
    op.alter_column('tickets', 'priority_id', existing_type=sa.Integer(), nullable=False)

    op.drop_constraint('ck_tickets_priority', 'tickets', type_='check')
    op.drop_column('tickets', 'priority')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('tickets', sa.Column('priority', sa.String(length=20), nullable=True))
    op.execute(
        f"""
        UPDATE tickets
        SET tickets.priority = ({_TITLE_TO_ENUM_CASE})
        FROM tickets
        INNER JOIN priorities ON priorities.id = tickets.priority_id
        """
    )
    op.alter_column('tickets', 'priority', existing_type=sa.String(length=20), nullable=False)
    op.create_check_constraint(
        'ck_tickets_priority', 'tickets', "priority IN ('LOW','MEDIUM','HIGH','CRITICAL')"
    )

    op.drop_column('tickets', 'location')
    op.drop_constraint('fk_tickets_priority_id_priorities', 'tickets', type_='foreignkey')
    op.drop_column('tickets', 'priority_id')

    op.drop_table('priorities')
