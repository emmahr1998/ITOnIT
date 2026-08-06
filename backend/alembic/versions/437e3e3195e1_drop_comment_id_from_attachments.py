"""drop comment_id from attachments

Revision ID: 437e3e3195e1
Revises: b8c5e972dfbf
Create Date: 2026-07-31 14:18:55.148372

An attachment now belongs to exactly one entity - its ticket - not
optionally to a ticket and a comment. `comment_id` was never actually set
by the application (AttachmentService.upload_attachment only ever set
ticket_id), so no data migration is needed here, only a column drop.

The original FK on this column was never given an explicit name, so SQL
Server auto-generated one; that name is looked up at migration-run time
via inspection rather than hardcoded, so this migration works regardless
of what a given database happened to name it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '437e3e3195e1'
down_revision: Union[str, Sequence[str], None] = 'b8c5e972dfbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys('attachments'):
        if fk['constrained_columns'] == ['comment_id']:
            op.drop_constraint(fk['name'], 'attachments', type_='foreignkey')
            break

    op.drop_column('attachments', 'comment_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('attachments', sa.Column('comment_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_attachments_comment_id_comments', 'attachments', 'comments', ['comment_id'], ['id']
    )
