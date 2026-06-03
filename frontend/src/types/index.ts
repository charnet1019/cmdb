// User types
export interface User {
  id: number
  username: string
  email: string
  full_name: string | null
  phone: string | null
  is_active: boolean
  mfa_enabled: boolean
  last_login_at: string | null
  created_at: string
  groups: Group[]
}

export interface Group {
  id: number
  name: string
  description?: string
  member_count?: number
  created_at?: string
}

// Asset types
export interface Asset {
  id: string  // UUID string from backend
  name: string
  asset_code: string | null
  category: AssetCategory
  internal_address: string | null
  external_address: string | null
  platform: string | null  // 物理机/虚拟机/RDS/Docker/Kubernetes
  status: string | null  // AssetStatus
  db_type: string | null  // 数据库类型：MySQL/PostgreSQL/MongoDB/Redis
  organization_id: number | null
  organization_name?: string | null
  device_type: string | null
  vendor: string | null
  model: string | null
  serial_number: string | null
  cpu: string | null
  memory: string | null
  system_disk: string | null
  data_disk: string | null
  notes: string | null
  extra_data: Record<string, any> | null
  applicant: string | null  // 申请人
  namespace: string | null  // 命名空间（数据库 Schema 等）
  owner_id: number | null  // 负责人 ID
  owner_name: string | null  // 负责人姓名
  version: string | null  // 版本（数据库）
  // OOB fields (for host category)
  oob_address: string | null  // OOB 管理地址
  oob_username: string | null  // OOB 用户名
  created_at: string
  updated_at: string
  credentials: CredentialSimple[]
  runs_on_hosts: AssetSimple[]
  storage_locations: StorageLocation[]
}

export type AssetCategory = 'host' | 'network' | 'database' | 'cloud' | 'web' | 'gpt'

export type AssetStatus = 'inventory' | 'deploying' | 'running' | 'maintenance' | 'deactivated' | 'pending_scrap' | 'scrapped' | 'returned'

export interface Credential {
  id: number
  asset_id: number
  username: string
  credential_type: string
  password?: string
  metadata?: Record<string, any>
  created_at: string
}

export interface CredentialSimple {
  id: number
  username: string
  credential_type: string
}

// Organization types
export interface Organization {
  id: number
  name: string
  parent_id: number | null
  path: string | null
  level: number
  count: number  // Direct asset count
  total_count?: number  // Total count including children
  children: Organization[]
}

// Authorization types
export interface Authorization {
  id: number
  entity_type: 'user' | 'group'
  entity_id: number
  target_type: 'asset' | 'asset_group'
  target_id: number
  permissions: string[]
  valid_from: string | null
  valid_until: string | null
  is_active: boolean
  created_by: number | null
  created_at: string
}

// Log types
export interface LoginLog {
  id: number
  username: string | null
  ip_address: string | null
  user_agent: string | null
  status: string
  failure_reason: string | null
  created_at: string
}

export interface OperationLog {
  id: number
  user_id: number | null
  action: string
  resource_type: string | null
  resource_id: number | null
  details: Record<string, any> | null
  ip_address: string | null
  status: string
  created_at: string
}

// API Response types
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

// Auth types
export interface LoginRequest {
  username: string
  password: string
  remember?: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_at: string
  user: UserSimple
}

export interface UserSimple {
  id: number
  username: string
  full_name: string | null
  email: string
}

export interface AssetSimple {
  id: string
  name: string
  internal_address: string | null
}

export interface StorageLocation {
  id: number
  path: string
  path_type: string  // data, log, backup, temp
  description: string | null
  created_at: string
}