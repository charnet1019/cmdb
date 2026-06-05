"""add version to user_preferences

Revision ID: a68006c5ccb8
Revises: a1f9194f3cdd
Create Date: 2026-06-04 17:34:29.337652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a68006c5ccb8'
down_revision: Union[str, None] = 'a1f9194f3cdd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_preferences',
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text("'1'")),
    )


def downgrade() -> None:
    op.drop_column('user_preferences', 'version')
