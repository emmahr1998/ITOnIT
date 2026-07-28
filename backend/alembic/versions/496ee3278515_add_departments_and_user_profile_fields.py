"""add departments and user profile fields

Revision ID: 496ee3278515
Revises: 42ac9b9a44ba
Create Date: 2026-07-28 09:56:55.188388

Adds the departments table and the new User profile fields (username,
phone_number, theme, department_id), replacing the old free-text
`users.department` string column with a proper foreign key.

Safe for existing data: any distinct non-null legacy `department` string is
turned into a real Department row and every user with that value is
re-pointed at it via department_id, before the old column is dropped.
`username` is backfilled from the email's local part (the substring before
"@") for any existing user that doesn't already have one, then constrained
NOT NULL + UNIQUE. This assumes no two existing users share the same email
local part - true for the current dataset; a genuine collision would abort
the migration with a constraint violation rather than silently overwrite data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '496ee3278515'
down_revision: Union[str, Sequence[str], None] = '42ac9b9a44ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('title'),
    )

    op.add_column('users', sa.Column('username', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('phone_number', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('theme', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('department_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_users_department_id_departments', 'users', 'departments', ['department_id'], ['id']
    )

    # Data migration: legacy department strings -> real Department rows.
    op.execute(
        """
        INSERT INTO departments (title, created_at, updated_at)
        SELECT DISTINCT department, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM users
        WHERE department IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE u
        SET u.department_id = d.id
        FROM users u
        INNER JOIN departments d ON d.title = u.department
        WHERE u.department IS NOT NULL
        """
    )

    # Backfill username for existing rows, then lock the column down.
    op.execute(
        """
        UPDATE users
        SET username = LEFT(email, CHARINDEX('@', email) - 1)
        WHERE username IS NULL AND CHARINDEX('@', email) > 1
        """
    )
    op.alter_column('users', 'username', existing_type=sa.String(length=50), nullable=False)
    op.create_unique_constraint('uq_users_username', 'users', ['username'])

    op.drop_column('users', 'department')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('users', sa.Column('department', sa.String(length=100), nullable=True))
    op.execute(
        """
        UPDATE u
        SET u.department = d.title
        FROM users u
        INNER JOIN departments d ON d.id = u.department_id
        """
    )

    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.drop_constraint('fk_users_department_id_departments', 'users', type_='foreignkey')
    op.drop_column('users', 'department_id')
    op.drop_column('users', 'theme')
    op.drop_column('users', 'phone_number')
    op.drop_column('users', 'username')

    op.drop_table('departments')
