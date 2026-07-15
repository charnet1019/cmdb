"""add password_history table

Revision ID: 20260714_010000
Revises: 20260714_000000
Create Date: 2026-07-14 01:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260714_010000"
down_revision = "20260714_000000"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("password_history"):
        op.create_table(
            "password_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("idx_password_history_user_id", "password_history", ["user_id"])

    # Seed history with each user's current password hash so it's immediately
    # protected against reuse, without waiting for their next password change.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO password_history (user_id, password_hash, created_at)
            SELECT id, password_hash, now() FROM users
            """
        )
    )


def downgrade():
    op.drop_table("password_history")
