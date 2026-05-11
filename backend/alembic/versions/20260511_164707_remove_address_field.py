"""remove_address_field

Revision ID: d4ad4fd3f864
Revises: 7a0dc73e3304
Create Date: 2026-05-11 16:47:07.475346

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4ad4fd3f864'
down_revision: Union[str, None] = '7a0dc73e3304'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('assets', 'address')


def downgrade() -> None:
    op.add_column('assets', sa.Column('address', sa.String(length=255), nullable=True))