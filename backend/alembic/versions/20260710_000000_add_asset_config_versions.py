"""add asset config versions

Revision ID: 20260710_000000
Revises: 20260709_000000
Create Date: 2026-07-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260710_000000"
down_revision = "20260709_000000"
branch_labels = None
depends_on = None


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def _fk_exists(inspector, table_name: str, fk_name: str) -> bool:
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))


def _create_index_if_missing(inspector, name: str, table_name: str, columns: list[str], unique: bool = False):
    if not _index_exists(inspector, table_name, name):
        op.create_index(name, table_name, columns, unique=unique)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("asset_config_files"):
        op.create_table(
            "asset_config_files",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.String(length=36), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("current_version_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("asset_id"),
        )

    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, op.f("ix_asset_config_files_id"), "asset_config_files", ["id"])
    _create_index_if_missing(inspector, op.f("ix_asset_config_files_asset_id"), "asset_config_files", ["asset_id"], unique=True)
    _create_index_if_missing(inspector, op.f("ix_asset_config_files_current_version_id"), "asset_config_files", ["current_version_id"])
    _create_index_if_missing(inspector, op.f("ix_asset_config_files_created_by"), "asset_config_files", ["created_by"])
    _create_index_if_missing(inspector, op.f("ix_asset_config_files_updated_by"), "asset_config_files", ["updated_by"])
    _create_index_if_missing(inspector, "idx_asset_config_files_asset_id", "asset_config_files", ["asset_id"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("asset_config_versions"):
        op.create_table(
            "asset_config_versions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("config_file_id", sa.Integer(), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("content_encrypted", sa.Text(), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("checksum", sa.String(length=64), nullable=False),
            sa.Column("change_summary", sa.String(length=255), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["config_file_id"], ["asset_config_files.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("config_file_id", "version_no", name="uq_asset_config_versions_file_version"),
        )

    inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, op.f("ix_asset_config_versions_id"), "asset_config_versions", ["id"])
    _create_index_if_missing(inspector, op.f("ix_asset_config_versions_config_file_id"), "asset_config_versions", ["config_file_id"])
    _create_index_if_missing(inspector, op.f("ix_asset_config_versions_checksum"), "asset_config_versions", ["checksum"])
    _create_index_if_missing(inspector, op.f("ix_asset_config_versions_created_by"), "asset_config_versions", ["created_by"])
    _create_index_if_missing(inspector, op.f("ix_asset_config_versions_created_at"), "asset_config_versions", ["created_at"])
    _create_index_if_missing(inspector, "idx_asset_config_versions_file_created", "asset_config_versions", ["config_file_id", "created_at"])

    inspector = sa.inspect(bind)
    if not _fk_exists(inspector, "asset_config_files", "fk_asset_config_files_current_version_id"):
        op.create_foreign_key(
            "fk_asset_config_files_current_version_id",
            "asset_config_files",
            "asset_config_versions",
            ["current_version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("asset_config_files") and _fk_exists(inspector, "asset_config_files", "fk_asset_config_files_current_version_id"):
        op.drop_constraint("fk_asset_config_files_current_version_id", "asset_config_files", type_="foreignkey")

    inspector = sa.inspect(bind)
    if inspector.has_table("asset_config_versions"):
        for index_name in [
            "idx_asset_config_versions_file_created",
            op.f("ix_asset_config_versions_created_at"),
            op.f("ix_asset_config_versions_created_by"),
            op.f("ix_asset_config_versions_checksum"),
            op.f("ix_asset_config_versions_config_file_id"),
            op.f("ix_asset_config_versions_id"),
        ]:
            if _index_exists(inspector, "asset_config_versions", index_name):
                op.drop_index(index_name, table_name="asset_config_versions")
        op.drop_table("asset_config_versions")

    inspector = sa.inspect(bind)
    if inspector.has_table("asset_config_files"):
        for index_name in [
            "idx_asset_config_files_asset_id",
            op.f("ix_asset_config_files_updated_by"),
            op.f("ix_asset_config_files_created_by"),
            op.f("ix_asset_config_files_current_version_id"),
            op.f("ix_asset_config_files_asset_id"),
            op.f("ix_asset_config_files_id"),
        ]:
            if _index_exists(inspector, "asset_config_files", index_name):
                op.drop_index(index_name, table_name="asset_config_files")
        op.drop_table("asset_config_files")
