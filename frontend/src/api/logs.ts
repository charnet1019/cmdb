import { api } from './index'

// Types
export interface LoginLog {
  id: number
  user_id: number | null
  username: string
  ip_address: string | null
  user_agent: string | null
  status: 'success' | 'failed'
  failure_reason: string | null
  created_at: string
}

export interface LoginLogStats {
  today_total: number
  success_rate: number
  failed_count: number
}

export interface OperationLogChangeItem {
  field: string
  label: string
  before: string
  after: string
  summary: string
}

export interface OperationLog {
  id: number
  user_id: number | null
  username: string
  action: string
  action_label?: string
  resource_type: string
  resource_type_label?: string
  resource_id: number | null
  resource_name: string | number | null
  details: Record<string, any> | null
  detail_action?: string | null
  detail_action_label?: string | null
  operation_summary?: string
  change_items?: OperationLogChangeItem[]
  ip_address: string | null
  status: string
  created_at: string
}

export interface PasswordLog {
  id: number
  user_id: number | null
  username: string
  credential_id: number | null
  asset_name: string | null
  change_type: string
  changed_by: number | null
  changed_by_name: string
  ip_address: string | null
  status: string
  created_at: string
}

// Login Logs
export async function getLoginLogs(params: {
  page?: number
  limit?: number
  search?: string
  status?: string
  date_from?: string
  date_to?: string
}): Promise<{ items: LoginLog[]; total: number; stats: LoginLogStats }> {
  const response = await api.get('/logs/login', { params })
  return {
    items: response.data.data || [],
    total: response.data.meta?.total || 0,
    stats: response.data.stats || { today_total: 0, success_rate: 0, failed_count: 0 }
  }
}

// Operation Logs
export async function getOperationLogs(params: {
  page?: number
  limit?: number
  search?: string
  action?: string
  user_id?: number
  date_from?: string
  date_to?: string
}): Promise<{ items: OperationLog[]; total: number }> {
  const response = await api.get('/logs/operation', { params })
  return {
    items: response.data.data || [],
    total: response.data.meta?.total || 0
  }
}

// Password Change Logs
export async function getPasswordLogs(params: {
  page?: number
  limit?: number
  search?: string
  user_id?: number
  change_type?: string
  date_from?: string
  date_to?: string
}): Promise<{ items: PasswordLog[]; total: number }> {
  const response = await api.get('/logs/password', { params })
  return {
    items: response.data.data || [],
    total: response.data.meta?.total || 0
  }
}