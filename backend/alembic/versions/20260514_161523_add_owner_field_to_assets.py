"""add_owner_field_to_assets

Revision ID: 5304b835fe28
Revises: d637e3471b97
Create Date: 2026-05-14 16:15:23.282817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5304b835fe28'
down_revision: Union[str, None] = 'd637e3471b97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add owner_id and owner_name columns
    op.add_column('assets', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.add_column('assets', sa.Column('owner_name', sa.String(length=100), nullable=True))

    # Add foreign key constraint
    op.create_foreign_key('fk_assets_owner_id', 'assets', 'users', ['owner_id'], ['id'])

    # Add index for faster lookups
    op.create_index('idx_assets_owner_id', 'assets', ['owner_id'])


def downgrade() -> None:
    # Drop index
    op.drop_index('idx_assets_owner_id', table_name='assets')

    # Drop foreign key
    op.drop_constraint('fk_assets_owner_id', 'assets', type_='foreignkey')

    # Drop columns
    op.drop_column('assets', 'owner_name')
    op.drop_column('assets', 'owner_id')