"""add_status_to_password_change_logs

Revision ID: 5b508b0777d5
Revises: 01e6ac10cbf0
Create Date: 2026-06-30 17:15:33.448969

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b508b0777d5'
down_revision: Union[str, None] = '01e6ac10cbf0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('password_change_logs', sa.Column('status', sa.String(20), nullable=True))
    op.execute("UPDATE password_change_logs SET status = 'success' WHERE status IS NULL")
    op.alter_column('password_change_logs', 'status', nullable=False)


def downgrade() -> None:
    op.drop_column('password_change_logs', 'status')