"""
Pydantic Schemas
Request/Response models for API
"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ============== Common ==============
class ResponseBase(BaseModel):
    """Base response model"""
    code: int = 0
    message: str = "success"


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
    group_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None
    mfa_enabled: Optional[bool] = None


class UserResponse(UserBase):
    """User response schema"""
    id: int
    is_active: bool
    mfa_enabled: bool
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

    model_config = ConfigDict(from_attributes=True)


# ============== Group Schemas ==============
class GroupBase(BaseModel):
    """Base group schema"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class GroupCreate(GroupBase):
    """Group creation schema"""
    initial_member_ids: Optional[List[int]] = []


class GroupUpdate(BaseModel):
    """Group update schema"""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class GroupResponse(GroupBase):
    """Group response schema"""
    id: int
    created_at: datetime
    member_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class GroupSimple(BaseModel):
    """Simple group schema for nested responses"""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


# ============== Asset Schemas ==============
class AssetBase(BaseModel):
    """Base asset schema"""
    name: str = Field(..., min_length=1, max_length=100)
    category: str
    address: Optional[str] = Field(None, max_length=255)
    internal_address: Optional[str] = None  # 内网地址
    external_address: Optional[str] = None  # 外网地址
    platform: Optional[str] = Field(None, max_length=50)
    organization_id: Optional[int] = None
    notes: Optional[str] = None
    # URL fields for cloud/web/gpt
    url: Optional[str] = Field(None, max_length=500)  # Legacy field for backward compatibility
    internal_url: Optional[str] = None  # 内网 URL
    external_url: Optional[str] = None  # 外网 URL


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
    extra_data: Optional[dict] = Field(None, serialization_alias="metadata")


class AssetUpdate(BaseModel):
    """Asset update schema"""
    name: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None
    internal_address: Optional[str] = None
    external_address: Optional[str] = None
    platform: Optional[str] = None
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
    is_active: Optional[bool] = None
    # URL fields
    internal_url: Optional[str] = None
    external_url: Optional[str] = None


class AssetResponse(AssetBase):
    """Asset response schema"""
    id: str
    asset_code: Optional[str]
    organization_name: Optional[str] = None
    device_type: Optional[str]
    vendor: Optional[str]
    model: Optional[str]
    serial_number: Optional[str]
    cpu: Optional[str]
    memory: Optional[str]
    system_disk: Optional[str]
    data_disk: Optional[str]
    extra_data: Optional[dict] = None
    is_active: bool
    created_at: datetime
    credentials: List["CredentialSimple"] = []

    model_config = ConfigDict(from_attributes=True)


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
    target_id: int
    permissions: List[str]
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class AuthorizationCreate(AuthorizationBase):
    """Authorization creation schema"""
    pass


class AuthorizationUpdate(BaseModel):
    """Authorization update schema"""
    permissions: Optional[List[str]] = None
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