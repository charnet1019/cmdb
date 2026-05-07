"""
Add internal_url and external_url fields to assets table

Revision ID: 20260507_url_split
Revises: 20260410_150734_add_host_hardware_fields
Create Date: 2026-05-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260507_url_split'
down_revision: Union[str, None] = '3b2afbd3a3b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns for internal and external URLs
    op.add_column('assets', sa.Column('internal_url', sa.Text(), nullable=True))
    op.add_column('assets', sa.Column('external_url', sa.Text(), nullable=True))

    # Migrate existing url data to external_url for cloud/web/gpt assets
    op.execute("""
        UPDATE assets
        SET external_url = url
        WHERE category IN ('cloud', 'web', 'gpt') AND url IS NOT NULL
    """)


def downgrade() -> None:
    # Migrate external_url back to url before dropping (optional, for data preservation)
    op.execute("""
        UPDATE assets
        SET url = COALESCE(external_url, url)
        WHERE category IN ('cloud', 'web', 'gpt')
    """)

    op.drop_column('assets', 'external_url')
    op.drop_column('assets', 'internal_url')
