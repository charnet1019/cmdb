"""add notifications

Revision ID: 20260709_000000
Revises: 20260707_session_minutes
Create Date: 2026-07-09 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260709_000000"
down_revision = "20260707_session_minutes"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def upgrade():
    if not _has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("sender_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("notification_receipts"):
        op.create_table(
            "notification_receipts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("notification_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_id ON notifications (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_sender_id ON notifications (sender_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notification_receipts_id ON notification_receipts (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notification_receipts_notification_id ON notification_receipts (notification_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notification_receipts_user_id ON notification_receipts (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notification_receipts_read_at ON notification_receipts (read_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notification_receipts_created_at ON notification_receipts (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_notification_receipts_user_read ON notification_receipts (user_id, read_at)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_receipts_unique ON notification_receipts (notification_id, user_id)")


def downgrade():
    op.drop_index("idx_notification_receipts_unique", table_name="notification_receipts")
    op.drop_index("idx_notification_receipts_user_read", table_name="notification_receipts")
    op.drop_index(op.f("ix_notification_receipts_created_at"), table_name="notification_receipts")
    op.drop_index(op.f("ix_notification_receipts_read_at"), table_name="notification_receipts")
    op.drop_index(op.f("ix_notification_receipts_user_id"), table_name="notification_receipts")
    op.drop_index(op.f("ix_notification_receipts_notification_id"), table_name="notification_receipts")
    op.drop_index(op.f("ix_notification_receipts_id"), table_name="notification_receipts")
    op.drop_table("notification_receipts")

    op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_sender_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")
