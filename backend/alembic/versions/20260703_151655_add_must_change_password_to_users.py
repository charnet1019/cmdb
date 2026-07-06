"""add_must_change_password_to_users

Revision ID: 8bdc88cb0e9a
Revises: 9801f7d4c02f
Create Date: 2026-07-03 15:16:55.788622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8bdc88cb0e9a'
down_revision: Union[str, None] = '9801f7d4c02f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default="f"),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")