"""drop is_active column from assets table

Revision ID: b9b3240807e1
Revises: 124b1c87ac33
Create Date: 2026-06-03 10:56:17.984655

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9b3240807e1'
down_revision: Union[str, None] = '124b1c87ac33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_index("idx_assets_is_active")
        batch_op.drop_column("is_active")


def downgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")))
        batch_op.create_index("idx_assets_is_active", "is_active")