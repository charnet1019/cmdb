"""
Pydantic Schemas
Request/Response models for API
"""
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


# ============== Common ==============
class ResponseBase(BaseModel):
    """Base response model"""
    code: int = 0
    message: str = "success"
    data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(exclude_none=True)


class PaginationMeta(BaseModel):
    """Pagination metadata"""
    total: int
    page: int
    limit: int
    pages: int


# ============== User Schemas ==============
class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8, max_length=32)
    group_ids: Optional[List[int]] = []
    is_active: bool = True
    mfa_enabled: bool = False


class UserUpdate(BaseModel):
    """User update schema"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    avatar_url: Optional[str] = Field(None, max_length=500)
    group_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    mfa_enabled: Optional[bool] = None


class UserResponse(UserBase):
    """User response schema"""
    id: int
    is_active: bool
    mfa_enabled: bool
    mfa_bound: bool = False  # True if mfa_secret is set
    avatar_url: Optional[str] = None
    last_login_at: Optional[datetime]
    created_at: datetime
    groups: List["GroupSimple"] = []

    model_config = ConfigDict(from_attributes=True)


class UserSimple(BaseModel):
    """Simple user schema for nested responses"""
    id: int
    username: str
    full_name: Optional[str]
    email: str
    avatar_url: Optional[str] = None
    is_superuser: bool = False
    permissions: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class UserDetailResponse(ResponseBase):
    """Single user detail response schema"""
    data: UserResponse


# ============== Group Schemas ==============
class GroupBase(BaseModel):
    """Base group schema"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class GroupCreate(GroupBase):
    """Group creation schema"""
    initial_member_ids: Optional[List[int]] = []
    is_default: bool = False


class GroupUpdate(BaseModel):
    """Group update schema"""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_default: Optional[bool] = None


class GroupResponse(GroupBase):
    """Group response schema"""
    id: int
    is_default: bool = False
    created_at: datetime
    member_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class GroupSimple(BaseModel):
    """Simple group schema for nested responses"""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class GroupDetailResponse(ResponseBase):
    """Single group detail response schema"""
    data: GroupResponse


# ============== Asset Schemas ==============
class AssetBase(BaseModel):
    """Base asset schema"""
    name: str = Field(..., min_length=1, max_length=100)
    category: str
    internal_address: Optional[str] = None  # 内网地址
    external_address: Optional[str] = None  # 外网地址
    platform: Optional[str] = Field(None, max_length=50)
    db_type: Optional[str] = Field(None, max_length=50)  # 数据库类型
    organization_id: Optional[int] = None
    notes: Optional[str] = None
    # Additional fields
    applicant: Optional[str] = Field(None, max_length=100)  # 申请人
    namespace: Optional[str] = Field(None, max_length=100)  # 命名空间
    owner_id: Optional[int] = None  # 负责人 ID
    owner_name: Optional[str] = Field(None, max_length=100)  # 负责人姓名


class StorageLocationCreate(BaseModel):
    """Storage location creation schema"""
    path: str = Field(..., max_length=500)
    path_type: str = Field(..., max_length=50)  # data, log, backup, temp
    description: Optional[str] = Field(None, max_length=200)


class StorageLocationResponse(BaseModel):
    """Storage location response schema"""
    id: int
    path: str
    path_type: str
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetCreate(AssetBase):
    """Asset creation schema"""
    asset_code: Optional[str] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    cpu: Optional[str] = None
    memory: Optional[str] = None
    system_disk: Optional[str] = None
    data_disk: Optional[str] = None
    db_type: Optional[str] = None
    applicant: Optional[str] = None
    namespace: Optional[str] = None
    status: Optional[str] = Field(None, max_length=50)  # AssetStatus
    extra_data: Optional[dict] = Field(None, serialization_alias="metadata")
    # OOB fields (for host category)
    oob_address: Optional[str] = Field(None, max_length=200)  # OOB 地址
    oob_username: Optional[str] = Field(None, max_length=100)  # OOB 用户名
    oob_password: Optional[str] = Field(None, max_length=255)  # OOB 密码（明文输入，后端加密）
    # Database asset fields
    host_ids: Optional[List[str]] = None  # Runs on hosts (for database category)
    storage_locations: Optional[List[StorageLocationCreate]] = None  # Storage paths (for database category)


class AssetUpdate(BaseModel):
    """Asset update schema"""
    name: Optional[str] = Field(None, max_length=100)
    asset_code: Optional[str] = None  # CI 编号
    internal_address: Optional[str] = None
    external_address: Optional[str] = None
    platform: Optional[str] = None
    db_type: Optional[str] = Field(None, max_length=50)  # 数据库类型
    organization_id: Optional[int] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    cpu: Optional[str] = None
    memory: Optional[str] = None
    system_disk: Optional[str] = None
    data_disk: Optional[str] = None
    notes: Optional[str] = None
    extra_data: Optional[dict] = None
    # Additional fields
    applicant: Optional[str] = Field(None, max_length=100)  # 申请人
    namespace: Optional[str] = Field(None, max_length=100)  # 命名空间
    owner_id: Optional[int] = None  # 负责人 ID
    owner_name: Optional[str] = Field(None, max_length=100)  # 负责人姓名
    # OOB fields (for host category)
    oob_address: Optional[str] = Field(None, max_length=200)  # OOB 地址
    oob_username: Optional[str] = Field(None, max_length=100)  # OOB 用户名
    oob_password: Optional[str] = Field(None, max_length=255)  # OOB 密码（明文输入，后端加密）
    # Database asset fields
    host_ids: Optional[List[str]] = None  # Runs on hosts (for database category)
    storage_locations: Optional[List[StorageLocationCreate]] = None  # Storage paths (for database category)
    status: Optional[str] = Field(None, max_length=50)  # AssetStatus


class AssetResponse(AssetBase):
    """Asset response schema"""
    id: str
    asset_code: Optional[str] = None
    organization_name: Optional[str] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    cpu: Optional[str] = None
    memory: Optional[str] = None
    system_disk: Optional[str] = None
    data_disk: Optional[str] = None
    extra_data: Optional[dict] = None
    status: Optional[str] = None  # AssetStatus
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    credentials: List["CredentialSimple"] = []
    applicant: Optional[str] = None
    namespace: Optional[str] = None
    owner_id: Optional[int] = None  # 负责人 ID
    owner_name: Optional[str] = Field(None, max_length=100)  # 负责人姓名
    # OOB fields (for host category, password not included in response)
    oob_address: Optional[str] = None
    oob_username: Optional[str] = None
    # Database asset fields
    runs_on_hosts: List["AssetSimple"] = []  # Hosts this database runs on
    storage_locations: List["StorageLocationResponse"] = []  # Storage paths

    model_config = ConfigDict(from_attributes=True, exclude_none=True)

    @field_validator("extra_data", mode="before")
    @classmethod
    def filter_sensitive_data(cls, v):
        """Filter out sensitive data from extra_data (e.g., oob_password)"""
        if not v:
            return v
        # Return a copy without sensitive fields
        filtered = {k: v for k, v in v.items() if k not in ("oob_password",)}
        return filtered if filtered else None


class AssetSimple(BaseModel):
    """Simple asset schema"""
    id: str
    name: str
    category: str
    address: Optional[str]

    model_config = ConfigDict(from_attributes=True)


# ============== Credential Schemas ==============
class CredentialBase(BaseModel):
    """Base credential schema"""
    username: str = Field(..., max_length=100)
    credential_type: str = "password"


class CredentialCreate(CredentialBase):
    """Credential creation schema"""
    password: str
    metadata: Optional[dict] = None


class CredentialUpdate(BaseModel):
    """Credential update schema"""
    username: Optional[str] = None
    password: Optional[str] = None
    metadata: Optional[dict] = None


class CredentialResponse(CredentialBase):
    """Credential response schema"""
    id: int
    asset_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CredentialSimple(BaseModel):
    """Simple credential schema"""
    id: int
    username: str
    credential_type: str

    model_config = ConfigDict(from_attributes=True)


class CredentialDecryptResponse(BaseModel):
    """Credential decrypt response"""
    id: int
    username: str
    password: str


# ============== Authorization Schemas ==============
class AuthorizationBase(BaseModel):
    """Base authorization schema"""
    entity_type: str  # user, group
    entity_id: int
    target_type: str  # asset, asset_group (organization)
    target_ids: List[str]
    permissions: List[str]
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class AuthorizationCreate(AuthorizationBase):
    """Authorization creation schema"""
    pass


class AuthorizationUpdate(BaseModel):
    """Authorization update schema"""
    permissions: Optional[List[str]] = None
    target_ids: Optional[List[str]] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None


class AuthorizationResponse(AuthorizationBase):
    """Authorization response schema"""
    id: int
    is_active: bool
    created_by: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== Auth Schemas ==============
class LoginRequest(BaseModel):
    """Login request schema"""
    username: str
    password: str
    remember: bool = False


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserSimple


class LoginResponse(ResponseBase):
    """Login response schema"""
    data: TokenResponse


class CurrentUserResponse(ResponseBase):
    """Current user info response schema"""
    data: UserSimple

class PasswordResetRequest(BaseModel):
    """Password reset request"""
    method: str = "auto"  # auto, manual
    new_password: Optional[str] = None
    force_change: bool = True
    send_email: bool = True


class PasswordChangeRequest(BaseModel):
    """Password change request"""
    old_password: str
    new_password: str
    confirm_password: str


# ============== MFA Schemas ==============
class MFARequiredData(BaseModel):
    """MFA required data"""
    requires_mfa: bool = True
    user_id: int
    setup: bool = False  # True = needs binding (no secret yet)

class MFARequiredResponse(ResponseBase):
    """Response when MFA is required during login"""
    data: MFARequiredData

class MFAVerifyRequest(BaseModel):
    """TOTP verification request for login"""
    user_id: int
    code: str = Field(..., min_length=6, max_length=6)
    setup: bool = False  # True = first-time binding

class MFASetupQRData(BaseModel):
    """MFA setup QR data"""
    qr_code: str
    mfa_secret: str


# ============== Log Schemas ==============
class LoginLogResponse(BaseModel):
    """Login log response"""
    id: int
    username: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    status: str
    failure_reason: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationLogResponse(BaseModel):
    """Operation log response"""
    id: int
    user_id: Optional[int]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    details: Optional[dict]
    ip_address: Optional[str]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== Dashboard Schemas ==============
class DashboardStats(BaseModel):
    """Dashboard statistics"""
    is_authorized: bool = True
    total_assets: int
    total_users: int
    online_users: int
    alerts: int
    asset_type_distribution: List[dict]
    recent_logins: List[dict]


# ============== List Responses ==============
class UserListResponse(ResponseBase):
    """User list response"""
    data: List[UserResponse]
    meta: PaginationMeta


class GroupListResponse(ResponseBase):
    """Group list response"""
    data: List[GroupResponse]
    meta: PaginationMeta


class AssetListResponse(ResponseBase):
    """Asset list response"""
    data: List[AssetResponse]
    meta: PaginationMeta


class BulkUpdateRequest(BaseModel):
    """Bulk update request schema"""
    ids: List[str]
    data: dict


class BulkDeleteRequest(BaseModel):
    """Bulk delete request schema"""
    ids: List[str]


class AuthorizationListResponse(ResponseBase):
    """Authorization list response"""
    data: List[AuthorizationResponse]
    meta: PaginationMeta


# Update forward references
UserResponse.model_rebuild()
AssetResponse.model_rebuild()