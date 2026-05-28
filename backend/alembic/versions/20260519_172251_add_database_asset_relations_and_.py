"""Add database asset relations and storage locations

Revision ID: 756932b10291
Revises: 3b3ddf61a3ee
Create Date: 2026-05-19 17:22:51.008940

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '756932b10291'
down_revision: Union[str, None] = '3b3ddf61a3ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create asset_host_relations table
    op.create_table(
        'asset_host_relations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.String(length=36), nullable=False),
        sa.Column('host_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['host_id'], ['assets.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_asset_host_relations_id', 'asset_host_relations', ['id'])
    op.create_index('idx_asset_host_relations_asset_id', 'asset_host_relations', ['asset_id'])
    op.create_index('idx_asset_host_relations_host_id', 'asset_host_relations', ['host_id'])
    op.create_index('idx_asset_host_unique', 'asset_host_relations', ['asset_id', 'host_id'], unique=True)

    # Create storage_locations table
    op.create_table(
        'storage_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.String(length=36), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('path_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_storage_locations_id', 'storage_locations', ['id'])
    op.create_index('idx_storage_locations_asset_id', 'storage_locations', ['asset_id'])
    op.create_index('idx_storage_asset_type', 'storage_locations', ['asset_id', 'path_type'])


def downgrade() -> None:
    op.drop_index('idx_storage_asset_type', table_name='storage_locations')
    op.drop_index('idx_storage_locations_asset_id', table_name='storage_locations')
    op.drop_index('idx_storage_locations_id', table_name='storage_locations')
    op.drop_table('storage_locations')

    op.drop_index('idx_asset_host_unique', table_name='asset_host_relations')
    op.drop_index('idx_asset_host_relations_host_id', table_name='asset_host_relations')
    op.drop_index('idx_asset_host_relations_asset_id', table_name='asset_host_relations')
    op.drop_index('idx_asset_host_relations_id', table_name='asset_host_relations')
    op.drop_table('asset_host_relations')