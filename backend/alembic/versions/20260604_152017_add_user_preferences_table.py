"""add user_preferences table

Revision ID: a1f9194f3cdd
Revises: b9b3240807e1
Create Date: 2026-06-04 15:20:17.858733

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f9194f3cdd'
down_revision: Union[str, None] = 'b9b3240807e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('column_visibility', sa.JSON(), nullable=True),
        sa.Column('column_order', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'category', name='idx_user_preferences_user_category'),
    )
    op.create_index('ix_user_preferences_id', 'user_preferences', ['id'], unique=False)
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'], unique=False)
    op.create_index('ix_user_preferences_category', 'user_preferences', ['category'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_user_preferences_category', table_name='user_preferences')
    op.drop_index('ix_user_preferences_user_id', table_name='user_preferences')
    op.drop_index('ix_user_preferences_id', table_name='user_preferences')
    op.drop_table('user_preferences')
