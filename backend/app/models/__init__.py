"""
Database Models
SQLAlchemy ORM models for CMDB
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4
from sqlalchemy import (
    String, Text, Boolean, Integer, DateTime, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
import enum
from app.database import Base


class AssetCategory(str, enum.Enum):
    """Asset category enumeration"""
    HOST = "host"
    NETWORK = "network"
    DATABASE = "database"
    CLOUD = "cloud"
    WEB = "web"
    GPT = "gpt"


class PermissionType(str, enum.Enum):
    """Permission type enumeration"""
    VIEW = "view"                    # 查看资产
    MANAGE = "manage"                # 管理资产
    USER_MGMT = "user_mgmt"          # 用户管理
    SYS_CONFIG = "sys_config"        # 系统设置
    AUDIT_LOG = "audit_log"          # 日志审计
    VIEW_PWD = "view_pwd"            # 查看复制资产密码
    MANAGE_PWD = "manage_pwd"        # 管理资产用户名密码


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
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(100))
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


class Asset(Base):
    """Asset model"""
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    asset_code: Mapped[Optional[str]] = mapped_column(String(50), unique=True)  # CI编号
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # AssetCategory
    address: Mapped[Optional[str]] = mapped_column(String(255))  # Legacy single address field
    internal_address: Mapped[Optional[str]] = mapped_column(Text)  # 内网地址(多行)
    external_address: Mapped[Optional[str]] = mapped_column(Text)  # 外网地址(多行)
    platform: Mapped[Optional[str]] = mapped_column(String(50))
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

    # Cloud/Web specific fields
    url: Mapped[Optional[str]] = mapped_column(String(500))  # Legacy field, kept for backward compatibility
    internal_url: Mapped[Optional[str]] = mapped_column(Text)  # 内网 URL(多行)
    external_url: Mapped[Optional[str]] = mapped_column(Text)  # 外网 URL(多行)

    # Notes field
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Additional metadata (renamed to avoid conflict with SQLAlchemy's metadata)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    credentials: Mapped[List["Credential"]] = relationship(
        "Credential", back_populates="asset", cascade="all, delete-orphan"
    )
    organization: Mapped[Optional["Organization"]] = relationship("Organization")

    __table_args__ = (
        Index("idx_assets_category", "category"),
        Index("idx_assets_organization_id", "organization_id"),
        Index("idx_assets_name", "name"),
        Index("idx_assets_is_active", "is_active"),
    )

    def __repr__(self):
        return f"<Asset {self.name}>"


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
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    permissions: Mapped[list] = mapped_column(JSONB, nullable=False)  # ["view", "manage", ...]
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime(False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    __table_args__ = (
        Index("idx_authorizations_entity", "entity_type", "entity_id"),
        Index("idx_authorizations_target", "target_type", "target_id"),
        Index("idx_authorizations_is_active", "is_active"),
    )

    def __repr__(self):
        return f"<Authorization {self.entity_type}:{self.entity_id} -> {self.target_type}:{self.target_id}>"


class LoginLog(Base):
    """Login log model"""
    __tablename__ = "login_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), index=True)
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
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # create, update, delete, authorize
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
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    credential_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("credentials.id"))
    change_type: Mapped[str] = mapped_column(String(20))  # user_password, asset_credential
    changed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_password_change_logs_user_id", "user_id"),
        Index("idx_password_change_logs_changed_by", "changed_by"),
    )


class Setting(Base):
    """System settings model"""
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[Optional[dict]] = mapped_column(JSONB)
    description: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Setting {self.key}>"