import api from './index'
import type { ApiResponse } from '@/types'

export interface DashboardStats {
  total_assets: number
  total_users: number
  active_users: number
  online_users: number
  asset_distribution: Array<{ type: string; count: number }>
  status_distribution: Array<{ name: string; count: number }>
  sub_distribution: Record<string, Array<{ name: string; count: number }>>
  recent_logins: Array<{ user: string; time: string; ip: string; user_id: number | null; is_online: boolean }>
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await api.get<ApiResponse<DashboardStats>>('/dashboard/stats')
  return response.data.data
}