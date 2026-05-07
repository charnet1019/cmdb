"""change asset id from int to uuid

Revision ID: 3b2afbd3a3b9
Revises: abc123def456
Create Date: 2026-05-06 15:08:20.379738

"""
from typing import Sequence, Union
from uuid import uuid4
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '3b2afbd3a3b9'
down_revision: Union[str, None] = 'abc123def456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # Step 1: Drop foreign key constraint first
    op.execute(text("ALTER TABLE credentials DROP CONSTRAINT credentials_asset_id_fkey"))

    # Step 2: Alter credentials.asset_id to VARCHAR
    op.alter_column('credentials', 'asset_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=36),
               existing_nullable=False)

    # Step 3: Fetch all existing assets
    result = connection.execute(text("SELECT * FROM assets"))
    rows = result.fetchall()

    # Step 4: Create mapping and prepare data
    id_mapping = {}
    insert_data = []

    for row in rows:
        old_id = row.id
        new_id = str(uuid4())
        id_mapping[old_id] = new_id
        insert_data.append({
            'id': new_id,
            'name': row.name,
            'asset_code': row.asset_code,
            'category': row.category,
            'address': row.address,
            'internal_address': row.internal_address,
            'external_address': row.external_address,
            'platform': row.platform,
            'organization_id': row.organization_id,
            'device_type': row.device_type,
            'vendor': row.vendor,
            'model': row.model,
            'serial_number': row.serial_number,
            'cpu': row.cpu,
            'memory': row.memory,
            'system_disk': row.system_disk,
            'data_disk': row.data_disk,
            'url': row.url,
            'notes': row.notes,
            'metadata': row.metadata,
            'is_active': row.is_active,
            'created_at': row.created_at,
            'updated_at': row.updated_at,
        })

    # Step 5: Create new assets table with UUID primary key
    op.execute(text("""
        CREATE TABLE assets_new (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            asset_code VARCHAR(50),
            category VARCHAR(50) NOT NULL,
            address VARCHAR(255),
            internal_address TEXT,
            external_address TEXT,
            platform VARCHAR(50),
            organization_id INTEGER,
            device_type VARCHAR(50),
            vendor VARCHAR(100),
            model VARCHAR(100),
            serial_number VARCHAR(100),
            cpu VARCHAR(100),
            memory VARCHAR(100),
            system_disk VARCHAR(100),
            data_disk VARCHAR(100),
            url VARCHAR(500),
            notes TEXT,
            metadata JSONB,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """))

    # Step 6: Insert data with new UUIDs
    if insert_data:
        for data in insert_data:
            if data['metadata'] is not None:
                data['metadata'] = json.dumps(data['metadata'])
            stmt = text("""
                INSERT INTO assets_new
                (id, name, asset_code, category, address, internal_address, external_address,
                 platform, organization_id, device_type, vendor, model, serial_number,
                 cpu, memory, system_disk, data_disk, url, notes, metadata, is_active,
                 created_at, updated_at)
                VALUES (:id, :name, :asset_code, :category, :address, :internal_address, :external_address,
                       :platform, :organization_id, :device_type, :vendor, :model, :serial_number,
                       :cpu, :memory, :system_disk, :data_disk, :url, :notes, :metadata, :is_active,
                       :created_at, :updated_at)
            """)
            connection.execute(stmt, data)

    # Step 7: Update credentials with new asset_ids
    for old_id, new_id in id_mapping.items():
        stmt = text("UPDATE credentials SET asset_id = :new_id WHERE asset_id = :old_id")
        connection.execute(stmt, {'new_id': new_id, 'old_id': str(old_id)})

    # Step 8: Drop old assets table
    op.execute(text("DROP TABLE assets"))

    # Step 9: Rename new table to assets
    op.execute(text("ALTER TABLE assets_new RENAME TO assets"))

    # Step 10: Recreate indexes
    op.execute(text("CREATE INDEX idx_assets_id ON assets(id)"))
    op.execute(text("CREATE INDEX idx_assets_category ON assets(category)"))
    op.execute(text("CREATE INDEX idx_assets_organization_id ON assets(organization_id)"))
    op.execute(text("CREATE INDEX idx_assets_name ON assets(name)"))
    op.execute(text("CREATE INDEX idx_assets_is_active ON assets(is_active)"))

    # Step 11: Recreate foreign key constraints
    op.execute(text("""
        ALTER TABLE assets
        ADD CONSTRAINT assets_organization_id_fkey
        FOREIGN KEY(organization_id) REFERENCES organizations(id)
    """))

    # Step 12: Recreate credentials foreign key
    op.execute(text("""
        ALTER TABLE credentials
        ADD CONSTRAINT credentials_asset_id_fkey
        FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
    """))


def downgrade() -> None:
    # Note: Downgrade is destructive - data will be lost
    # Reset to integer ids (sequential)
    op.execute(text("""
        CREATE TABLE assets_downgrade AS
        SELECT
            ROW_NUMBER() OVER () as id,
            name,
            asset_code,
            category,
            address,
            internal_address,
            external_address,
            platform,
            organization_id,
            device_type,
            vendor,
            model,
            serial_number,
            cpu,
            memory,
            system_disk,
            data_disk,
            url,
            notes,
            metadata as extra_data,
            is_active,
            created_at,
            updated_at
        FROM assets
    """))

    op.execute(text("DROP TABLE assets"))
    op.execute(text("ALTER TABLE assets_downgrade RENAME TO assets"))
    op.execute(text("ALTER TABLE assets ADD CONSTRAINT assets_pkey PRIMARY KEY (id)"))

    op.alter_column('credentials', 'asset_id',
               existing_type=sa.String(length=36),
               type_=sa.INTEGER(),
               existing_nullable=False)