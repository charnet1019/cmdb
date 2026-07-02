"""add_avatar_url_to_users

Revision ID: 9801f7d4c02f
Revises: 5b508b0777d5
Create Date: 2026-07-01 16:57:18.985847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9801f7d4c02f'
down_revision: Union[str, None] = '5b508b0777d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'avatar_url')