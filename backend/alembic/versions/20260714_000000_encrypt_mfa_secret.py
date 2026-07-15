"""encrypt plaintext mfa_secret values

Revision ID: 20260714_000000
Revises: 20260710_000000
Create Date: 2026-07-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260714_000000"
down_revision = "20260710_000000"
branch_labels = None
depends_on = None


def upgrade():
    # Fernet-encrypted secrets are ~140 chars, wider than the previous 100-char column.
    op.alter_column("users", "mfa_secret", type_=sa.String(255), existing_type=sa.String(100))

    # Reuse the app's own encryption module so this matches settings.ENCRYPTION_KEY
    # loaded from .env, rather than relying on it being exported to the process env.
    from app.core.encryption import encrypt_value

    connection = op.get_bind()
    result = connection.execute(
        sa.text("SELECT id, mfa_secret FROM users WHERE mfa_secret IS NOT NULL AND mfa_secret NOT LIKE 'gAAAA%'")
    )
    for user_id, mfa_secret in result:
        encrypted = encrypt_value(mfa_secret)
        connection.execute(
            sa.text("UPDATE users SET mfa_secret = :encrypted WHERE id = :user_id"),
            {"encrypted": encrypted, "user_id": user_id},
        )


def downgrade():
    from app.core.encryption import decrypt_value

    connection = op.get_bind()
    result = connection.execute(
        sa.text("SELECT id, mfa_secret FROM users WHERE mfa_secret LIKE 'gAAAA%'")
    )
    for user_id, mfa_secret in result:
        decrypted = decrypt_value(mfa_secret)
        connection.execute(
            sa.text("UPDATE users SET mfa_secret = :decrypted WHERE id = :user_id"),
            {"decrypted": decrypted, "user_id": user_id},
        )

    op.alter_column("users", "mfa_secret", type_=sa.String(100), existing_type=sa.String(255))
