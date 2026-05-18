"""add_oob_columns_to_asset

Revision ID: 3b3ddf61a3ee
Revises: 5304b835fe28
Create Date: 2026-05-15 17:07:49.581771

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b3ddf61a3ee'
down_revision: Union[str, None] = '5304b835fe28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new OOB columns to assets table
    op.add_column('assets', sa.Column('oob_address', sa.String(200), nullable=True))
    op.add_column('assets', sa.Column('oob_username', sa.String(100), nullable=True))
    op.add_column('assets', sa.Column('oob_password_encrypted', sa.Text(), nullable=True))

    # Create index for OOB address search
    op.create_index('idx_assets_oob_address', 'assets', ['oob_address'])

    # Migrate data from extra_data (metadata) to new columns
    # Import encryption module to encrypt existing plaintext passwords
    from cryptography.fernet import Fernet
    import base64
    import hashlib
    import os

    # Get encryption key from environment
    encryption_key = os.environ.get('ENCRYPTION_KEY')
    if encryption_key:
        # Derive Fernet key
        if len(encryption_key) == 44:
            key = encryption_key.encode()
        else:
            derived = hashlib.sha256(encryption_key.encode()).digest()
            key = base64.urlsafe_b64encode(derived)
        fernet = Fernet(key)
    else:
        fernet = None

    # Connect to database for data migration
    connection = op.get_bind()

    # Select all assets with extra_data containing OOB fields
    # Note: extra_data is stored in column named 'metadata' in the database
    result = connection.execute(
        sa.text("""
            SELECT id, "metadata" FROM assets
            WHERE "metadata" IS NOT NULL
            AND ("metadata"::text LIKE '%oob%' OR "metadata"::text LIKE '%oob_password%')
        """)
    )

    for row in result:
        asset_id = row[0]
        extra_data = row[1]

        if not isinstance(extra_data, dict):
            continue

        # Extract OOB fields
        oob_address = extra_data.get('oob')
        oob_username = extra_data.get('oob_username')
        oob_password = extra_data.get('oob_password')

        # Encrypt password if exists and fernet is available
        encrypted_password = None
        if oob_password:
            if fernet:
                try:
                    # Check if already encrypted (Fernet encrypted strings start with 'gAAAA')
                    if not oob_password.startswith('gAAAA'):
                        encrypted_password = fernet.encrypt(oob_password.encode()).decode()
                    else:
                        encrypted_password = oob_password
                except Exception:
                    encrypted_password = oob_password
            else:
                encrypted_password = oob_password

        # Update asset with new columns
        connection.execute(
            sa.text("""
                UPDATE assets
                SET oob_address = :oob_address,
                    oob_username = :oob_username,
                    oob_password_encrypted = :oob_password_encrypted
                WHERE id = :asset_id
            """),
            {
                'oob_address': oob_address,
                'oob_username': oob_username,
                'oob_password_encrypted': encrypted_password,
                'asset_id': asset_id
            }
        )

        # Clean up extra_data by removing OOB fields
        if extra_data:
            cleaned_data = {k: v for k, v in extra_data.items() if k not in ('oob', 'oob_username', 'oob_password')}
            if cleaned_data:
                connection.execute(
                    sa.text('UPDATE assets SET "metadata" = :cleaned_data WHERE id = :asset_id'),
                    {'cleaned_data': cleaned_data, 'asset_id': asset_id}
                )
            else:
                connection.execute(
                    sa.text('UPDATE assets SET "metadata" = NULL WHERE id = :asset_id'),
                    {'asset_id': asset_id}
                )


def downgrade() -> None:
    # Drop index
    op.drop_index('idx_assets_oob_address', table_name='assets')

    # Drop columns
    op.drop_column('assets', 'oob_password_encrypted')
    op.drop_column('assets', 'oob_username')
    op.drop_column('assets', 'oob_address')
