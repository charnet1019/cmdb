import api from './index'
import type { ApiResponse } from '@/types'

export interface DashboardStats {
  total_assets: number
  active_assets: number
  total_users: number
  active_users: number
  online_users: number
  asset_distribution: Array<{ type: string; count: number }>
  recent_logins: Array<{ user: string; time: string; ip: string; user_id: number | null }>
}

export interface DashboardAlerts {
  alerts: number
  failed_logins_24h: number
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await api.get<ApiResponse<DashboardStats>>('/dashboard/stats')
  return response.data.data
}

export async function getDashboardAlerts(): Promise<DashboardAlerts> {
  const response = await api.get<ApiResponse<DashboardAlerts>>('/dashboard/alerts')
  return response.data.data
}