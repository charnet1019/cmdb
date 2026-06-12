"""alter authorization target_id to string + add GIN index

Revision ID: 20260611_auth_target_id_str
Revises: 144036e4f912
Create Date: 2026-06-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260611_auth_target_id_str"
down_revision: Union[str, None] = "144036e4f912"
branch_labels: Union[str, None, None] = None
depends_on: Union[str, None, None] = None


def upgrade() -> None:
    # Drop existing index on target
    op.drop_index("idx_authorizations_target", table_name="authorizations")

    # Alter column type from integer to varchar(36)
    op.execute(
        "ALTER TABLE authorizations ALTER COLUMN target_id TYPE VARCHAR(36) USING target_id::VARCHAR(36)"
    )

    # Recreate index
    op.create_index(
        "idx_authorizations_target",
        "authorizations",
        ["target_type", "target_id"],
    )

    # Add GIN index on permissions for @> operator
    op.create_index(
        "idx_authorizations_permissions_gin",
        "authorizations",
        ["permissions"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("idx_authorizations_permissions_gin", table_name="authorizations")
    op.drop_index("idx_authorizations_target", table_name="authorizations")
    op.execute(
        "ALTER TABLE authorizations ALTER COLUMN target_id TYPE INTEGER USING target_id::INTEGER"
    )
    op.create_index(
        "idx_authorizations_target",
        "authorizations",
        ["target_type", "target_id"],
    )
