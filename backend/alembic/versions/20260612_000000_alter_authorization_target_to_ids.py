"""alter authorization target_id to target_ids JSONB array

Revision ID: 20260612_auth_target_ids
Revises: 20260611_auth_target_id_str
Create Date: 2026-06-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260612_auth_target_ids"
down_revision: Union[str, None] = "20260611_auth_target_id_str"
branch_labels: Union[str, None, None] = None
depends_on: Union[str, None, None] = None


def upgrade() -> None:
    # Add new target_ids column
    op.add_column("authorizations", sa.Column("target_ids", JSONB(), nullable=True))

    # Migrate existing data: target_id → [target_id]
    op.execute("UPDATE authorizations SET target_ids = jsonb_build_array(target_id)")

    # Make target_ids NOT NULL (all rows now have data)
    op.alter_column("authorizations", "target_ids", nullable=False)

    # Drop old index on (target_type, target_id)
    op.drop_index("idx_authorizations_target", table_name="authorizations")

    # Drop old column
    op.drop_column("authorizations", "target_id")

    # Create new indexes
    op.create_index(
        "idx_authorizations_target_type",
        "authorizations",
        ["target_type"],
    )
    op.create_index(
        "idx_authorizations_target_ids_gin",
        "authorizations",
        ["target_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    # Drop new indexes
    op.drop_index("idx_authorizations_target_ids_gin", table_name="authorizations")
    op.drop_index("idx_authorizations_target_type", table_name="authorizations")

    # Add back target_id column
    op.add_column(
        "authorizations",
        sa.Column("target_id", sa.VARCHAR(length=36), nullable=True),
    )

    # Extract first element from target_ids
    op.execute("UPDATE authorizations SET target_id = (target_ids->0)::text")
    op.alter_column("authorizations", "target_id", nullable=False)

    # Drop target_ids
    op.drop_column("authorizations", "target_ids")

    # Recreate old index
    op.create_index(
        "idx_authorizations_target",
        "authorizations",
        ["target_type", "target_id"],
    )
