"""add is_default column to groups table

Revision ID: c47f22a2faa6
Revises: a68006c5ccb8
Create Date: 2026-06-09 14:00:13.809290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c47f22a2faa6'
down_revision: Union[str, None] = 'a68006c5ccb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('groups', sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('false')))

def downgrade() -> None:
    op.drop_column('groups', 'is_default')
