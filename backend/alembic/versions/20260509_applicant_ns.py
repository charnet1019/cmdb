"""
Add applicant and namespace fields to assets table

Revision ID: 20260509_applicant_ns
Revises: 20260507_url_split
Create Date: 2026-05-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260509_applicant_ns'
down_revision: Union[str, None] = '20260507_url_split'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add applicant column (for tracking who requested the asset)
    op.add_column('assets', sa.Column('applicant', sa.String(100), nullable=True))

    # Add namespace column (for database schema/namespace)
    op.add_column('assets', sa.Column('namespace', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('assets', 'namespace')
    op.drop_column('assets', 'applicant')
