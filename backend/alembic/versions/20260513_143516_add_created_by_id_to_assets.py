"""add created_by_id to assets

Revision ID: d637e3471b97
Revises: f9adac0c344d
Create Date: 2026-05-13 14:35:16.633729

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd637e3471b97'
down_revision: Union[str, None] = 'f9adac0c344d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('created_by_id', sa.Integer(), nullable=True))
    op.create_index('idx_assets_created_by_id', 'assets', ['created_by_id'])
    op.create_foreign_key('fk_assets_created_by', 'assets', 'users', ['created_by_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_assets_created_by', 'assets', type_='foreignkey')
    op.drop_index('idx_assets_created_by_id', table_name='assets')
    op.drop_column('assets', 'created_by_id')