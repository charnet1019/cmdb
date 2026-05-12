"""remove_url_fields

Revision ID: f9adac0c344d
Revises: d4ad4fd3f864
Create Date: 2026-05-12 11:08:55.654423

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9adac0c344d'
down_revision: Union[str, None] = 'd4ad4fd3f864'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('assets', 'url')
    op.drop_column('assets', 'internal_url')
    op.drop_column('assets', 'external_url')


def downgrade() -> None:
    op.add_column('assets', sa.Column('external_url', sa.Text(), nullable=True))
    op.add_column('assets', sa.Column('internal_url', sa.Text(), nullable=True))
    op.add_column('assets', sa.Column('url', sa.String(length=500), nullable=True))