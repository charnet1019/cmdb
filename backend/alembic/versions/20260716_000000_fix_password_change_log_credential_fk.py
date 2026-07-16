"""fix_password_change_log_credential_fk

password_change_logs.credential_id had no ON DELETE behavior, so deleting a
credential with change-history rows raised an unhandled IntegrityError
(surfacing as a raw 500) instead of nulling the reference the way
user_id/changed_by already do.

Revision ID: 20260716_000000
Revises: 20260714_010000
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260716_000000"
down_revision: Union[str, None] = "20260714_010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_CONSTRAINT = "password_change_logs_credential_id_fkey"
NEW_CONSTRAINT = "fk_password_change_logs_credential_id"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE password_change_logs DROP CONSTRAINT {OLD_CONSTRAINT}, "
        f"ADD CONSTRAINT {NEW_CONSTRAINT} FOREIGN KEY (credential_id) "
        f"REFERENCES credentials(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE password_change_logs DROP CONSTRAINT {NEW_CONSTRAINT}, "
        f"ADD CONSTRAINT {OLD_CONSTRAINT} FOREIGN KEY (credential_id) "
        f"REFERENCES credentials(id)"
    )
