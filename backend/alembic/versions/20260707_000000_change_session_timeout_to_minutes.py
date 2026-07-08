"""reset_session_timeout_to_30_minutes

Revision ID: 20260707_session_minutes
Revises: 8bdc88cb0e9a
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260707_session_minutes"
down_revision: Union[str, None] = "8bdc88cb0e9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM settings WHERE key = 'session_timeout'")
    op.execute(
        """
        INSERT INTO settings (key, value, description, updated_at)
        VALUES ('session_timeout', '{"value": 30}'::jsonb, '会话超时时间(分钟)', now())
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM settings WHERE key = 'session_timeout'")
    op.execute(
        """
        INSERT INTO settings (key, value, description, updated_at)
        VALUES ('session_timeout', '{"value": 1}'::jsonb, '会话超时时间(小时)', now())
        """
    )
