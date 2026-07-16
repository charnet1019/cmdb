"""
Database Models
SQLAlchemy ORM models for CMDB
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4
from sqlalchemy import (
    String, Text, Boolean, Integer, DateTime, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
import enum
from app.database import Base


class AssetStatus(str, enum.Enum):
    """Asset lifecycle status enumeration"""
    INVENTORY = "inventory"           # 库存
    DEPLOYING = "deploying"           # 部署中
    RUNNING = "running"               # 运行中
    MAINTENANCE = "maintenance"       # 维护中
    DEACTIVATED = "deactivated"       # 停用
    PENDING_SCRAP = "pending_scrap"   # 待报废
    SCRAPPED = "scrapped"             # 已报废
    RETURNED = "returned"             # 已退还


class User(Base):
    """User model"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(255))  # Fernet-encrypted; ~140 chars
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    groups: Mapped[List["Group"]] = relationship(
        "Group", secondary="user_groups", back_populates="users"
    )

    def __repr__(self):
        return f"<User {self.username}>"


class Group(Base):
    """User group model"""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    users: Mapped[List[User]] = relationship(
        "User", secondary="user_groups", back_populates="groups"
    )

    def __repr__(self):
        return f"<Group {self.name}>"


class UserGroup(Base):
    """User-Group association table"""
    __tablename__ = "user_groups"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    __table_args__ = (
        Index("idx_user_groups_user_id", "user_id"),
        Index("idx_user_groups_group_id", "group_id"),
    )


class Organization(Base):
    """Organization/Asset group model"""
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("organizations.id"))
    path: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Self-referential relationship
    children: Mapped[List["Organization"]] = relationship(
        "Organization", backref="parent", remote_side=[id]
    )

    def __repr__(self):
        return f"<Organization {self.name}>"


class AssetHostRelation(Base):
    """Many-to-many relationship between database assets and host assets"""
    __tablename__ = "asset_host_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)  # Database asset
    host_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)  # Host asset
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    database_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[asset_id])
    host_asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[host_id])

    __table_args__ = (
        Index("idx_asset_host_unique", "asset_id", "host_id", unique=True),
    )

    def __repr__(self):
        return f"<AssetHostRelation {self.asset_id} -> {self.host_id}>"


class StorageLocation(Base):
    """Storage locations for database assets"""
    __tablename__ = "storage_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)  # e.g., /var/lib/mysql
    path_type: Mapped[str] = mapped_column(String(50), nullable=False)  # data, log, backup, temp
    description: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    asset: Mapped["Asset"] = relationship("Asset")

    __table_args__ = (
        Index("idx_storage_asset_type", "asset_id", "path_type"),
    )

    def __repr__(self):
        return f"<StorageLocation {self.path_type}:{self.path}>"


class Asset(Base):
    """Asset model"""
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    asset_code: Mapped[Optional[str]] = mapped_column(String(50), unique=True)  # CI编号
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # host/network/database/cloud/web/gpt
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)  # 创建者 ID
    internal_address: Mapped[Optional[str]] = mapped_column(Text)  # 内网地址(多行)
    external_address: Mapped[Optional[str]] = mapped_column(Text)  # 外网地址(多行)
    platform: Mapped[Optional[str]] = mapped_column(String(50))  # 物理机/虚拟机/RDS/Docker/Kubernetes
    db_type: Mapped[Optional[str]] = mapped_column(String(50))  # 数据库类型：MySQL/PostgreSQL/MongoDB/Redis
    organization_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("organizations.id"))

    # Network device specific fields
    device_type: Mapped[Optional[str]] = mapped_column(String(50))  # 交换机/路由器/防火墙
    vendor: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    serial_number: Mapped[Optional[str]] = mapped_column(String(100))

    # Host hardware spec fields
    cpu: Mapped[Optional[str]] = mapped_column(String(100))  # 如: 8核
    memory: Mapped[Optional[str]] = mapped_column(String(100))  # 如: 16GB
    system_disk: Mapped[Optional[str]] = mapped_column(String(100))  # 如: 500GB SSD
    data_disk: Mapped[Optional[str]] = mapped_column(String(100))  # 如: 2TB HDD
    # OOB fields (for host category)
    oob_address: Mapped[Optional[str]] = mapped_column(String(200))  # OOB 管理地址
    oob_username: Mapped[Optional[str]] = mapped_column(String(100))  # OOB 用户名
    oob_password_encrypted: Mapped[Optional[str]] = mapped_column(Text)  # OOB 密码（加密）


    # Notes field
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Additional metadata (renamed to avoid conflict with SQLAlchemy's metadata)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)

    # Additional fields
    applicant: Mapped[Optional[str]] = mapped_column(String(100))  # 申请人
    namespace: Mapped[Optional[str]] = mapped_column(String(100))  # 命名空间（数据库 Schema 等）
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)  # 负责人 ID
    owner_name: Mapped[Optional[str]] = mapped_column(String(100))  # 负责人姓名（冗余字段）

    status: Mapped[Optional[str]] = mapped_column(String(50), index=True)  # AssetStatus
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    credentials: Mapped[List["Credential"]] = relationship(
        "Credential", back_populates="asset", cascade="all, delete-orphan"
    )
    organization: Mapped[Optional["Organization"]] = relationship("Organization")
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_id])
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id])
    # Database asset relationships
    database_hosts: Mapped[List["AssetHostRelation"]] = relationship(
        "AssetHostRelation", foreign_keys=[AssetHostRelation.asset_id], back_populates="database_asset", cascade="all, delete-orphan"
    )
    storage_locations: Mapped[List["StorageLocation"]] = relationship(
        "StorageLocation", back_populates="asset", cascade="all, delete-orphan"
    )
    config_file: Mapped[Optional["AssetConfigFile"]] = relationship(
        "AssetConfigFile", back_populates="asset", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        Index("idx_assets_category", "category"),
        Index("idx_assets_organization_id", "organization_id"),
        Index("idx_assets_name", "name"),
    )

    def __repr__(self):
        return f"<Asset {self.name}>"


class AssetConfigFile(Base):
    """Current network device configuration file metadata."""
    __tablename__ = "asset_config_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    current_version_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("asset_config_versions.id", ondelete="SET NULL", use_alter=True), index=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    asset: Mapped["Asset"] = relationship("Asset", back_populates="config_file")
    versions: Mapped[List["AssetConfigVersion"]] = relationship(
        "AssetConfigVersion", back_populates="config_file", cascade="all, delete-orphan", foreign_keys="AssetConfigVersion.config_file_id"
    )

    __table_args__ = (
        Index("idx_asset_config_files_asset_id", "asset_id"),
    )


class AssetConfigVersion(Base):
    """Versioned encrypted network device configuration content."""
    __tablename__ = "asset_config_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    config_file_id: Mapped[int] = mapped_column(Integer, ForeignKey("asset_config_files.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    change_summary: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)

    config_file: Mapped["AssetConfigFile"] = relationship("AssetConfigFile", back_populates="versions", foreign_keys=[config_file_id])

    __table_args__ = (
        UniqueConstraint("config_file_id", "version_no", name="uq_asset_config_versions_file_version"),
        Index("idx_asset_config_versions_file_created", "config_file_id", "created_at"),
    )


class Credential(Base):
    """Credential model for assets"""
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    credential_type: Mapped[str] = mapped_column(String(50), default="password")  # password, ssh_key, api_key, snmp
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)  # AKID, Secret, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    asset: Mapped[Asset] = relationship("Asset", back_populates="credentials")

    def __repr__(self):
        return f"<Credential {self.username}@{self.asset_id}>"


class Authorization(Base):
    """Authorization model"""
    __tablename__ = "authorizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # user, group
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)  # asset, asset_group
    target_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)  # asset UUIDs or org IDs
    permissions: Mapped[list] = mapped_column(JSONB, nullable=False)  # ["view", "manage", ...]
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    __table_args__ = (
        Index("idx_authorizations_entity", "entity_type", "entity_id"),
        Index("idx_authorizations_target_type", "target_type"),
        Index("idx_authorizations_target_ids_gin", "target_ids", postgresql_using="gin"),
        Index("idx_authorizations_is_active", "is_active"),
    )

    def __repr__(self):
        return f"<Authorization {self.entity_type}:{self.entity_id} -> {self.target_type}:{self.target_ids}>"


class Notification(Base):
    """In-app notification message."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sender_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)

    sender: Mapped[Optional["User"]] = relationship("User", foreign_keys=[sender_id])

    def __repr__(self):
        return f"<Notification {self.id}:{self.title}>"


class NotificationReceipt(Base):
    """Per-user notification delivery and read state."""
    __tablename__ = "notification_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    notification_id: Mapped[int] = mapped_column(Integer, ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(False), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)

    notification: Mapped["Notification"] = relationship("Notification")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("idx_notification_receipts_user_read", "user_id", "read_at"),
        Index("idx_notification_receipts_unique", "notification_id", "user_id", unique=True),
    )


class LoginLog(Base):
    """Login log model"""
    __tablename__ = "login_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    username: Mapped[Optional[str]] = mapped_column(String(50))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)  # success, failed
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_login_logs_user_id", "user_id"),
        Index("idx_login_logs_created_at", "created_at"),
        Index("idx_login_logs_status", "status"),
    )


class OperationLog(Base):
    """Operation log model"""
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # create, update, delete, authorize, download, import, export
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    resource_id: Mapped[Optional[int]] = mapped_column(Integer)
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    status: Mapped[str] = mapped_column(String(20), default="success")  # success, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_operation_logs_user_id", "user_id"),
        Index("idx_operation_logs_action", "action"),
        Index("idx_operation_logs_created_at", "created_at"),
    )


class PasswordChangeLog(Base):
    """Password change log model"""
    __tablename__ = "password_change_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("credentials.id", ondelete="SET NULL"))
    change_type: Mapped[str] = mapped_column(String(20))  # user_password, asset_credential
    changed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    status: Mapped[str] = mapped_column(String(20), default="success")  # success, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_password_change_logs_user_id", "user_id"),
        Index("idx_password_change_logs_changed_by", "changed_by"),
    )


class PasswordHistory(Base):
    """Previously used password hashes, for reuse-prevention checks"""
    __tablename__ = "password_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_password_history_user_id", "user_id"),
    )


class Setting(Base):
    """System settings model"""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[Optional[dict]] = mapped_column(JSONB)
    description: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def __repr__(self):
        return f"<Setting {self.key}>"


class UserPreference(Base):
    """User preference settings"""
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 'all', 'host', 'network', etc.
    column_visibility: Mapped[Optional[dict]] = mapped_column(JSONB)  # {"id": false, "status": true, ...}
    column_order: Mapped[Optional[list]] = mapped_column(JSONB)  # ["name", "address", "status", ...]
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")  # schema version for cache invalidation
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    __table_args__ = (
        Index("idx_user_preferences_user_category", "user_id", "category", unique=True),
    )

    def __repr__(self):
        return f"<UserPreference user={self.user_id} cat={self.category}>"