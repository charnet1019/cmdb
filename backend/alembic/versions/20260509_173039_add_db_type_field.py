"""add_db_type_field

Revision ID: 7a0dc73e3304
Revises: 20260509_applicant_ns
Create Date: 2026-05-09 17:30:39.397944

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a0dc73e3304'
down_revision: Union[str, None] = '20260509_applicant_ns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add db_type column for database type (MySQL/PostgreSQL/MongoDB/Redis)
    op.add_column('assets', sa.Column('db_type', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('assets', 'db_type')