"""add_status_to_assets

Revision ID: 124b1c87ac33
Revises: 756932b10291
Create Date: 2026-06-02 09:05:55.518641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '124b1c87ac33'
down_revision: Union[str, None] = '756932b10291'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('status', sa.String(50), nullable=True))
    op.create_index(op.f('ix_assets_status'), 'assets', ['status'])


def downgrade() -> None:
    op.drop_index(op.f('ix_assets_status'), table_name='assets')
    op.drop_column('assets', 'status')