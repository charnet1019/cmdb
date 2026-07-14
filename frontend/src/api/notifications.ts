import { api } from './index'
import type { NotificationItem, NotificationCreatePayload } from '@/types'

export async function getNotifications(params: {
  status?: 'all' | 'unread' | 'read'
  page?: number
  limit?: number
} = {}) {
  const response = await api.get('/notifications', { params })
  return {
    items: (response.data.data || []) as NotificationItem[],
    total: response.data.meta?.total || 0,
    page: response.data.meta?.page || 1,
    limit: response.data.meta?.limit || 20,
    pages: response.data.meta?.pages || 0,
  }
}

export async function getSentNotifications(params: {
  page?: number
  limit?: number
} = {}) {
  const response = await api.get('/notifications/sent', { params })
  return {
    items: (response.data.data || []) as NotificationItem[],
    total: response.data.meta?.total || 0,
    page: response.data.meta?.page || 1,
    limit: response.data.meta?.limit || 20,
    pages: response.data.meta?.pages || 0,
  }
}

export async function getUnreadCount(): Promise<number> {
  const response = await api.get('/notifications/unread-count')
  return response.data.data?.count || 0
}

export async function getCanSendNotification(): Promise<boolean> {
  const response = await api.get('/notifications/can-send')
  return response.data.data?.can_send || false
}

export async function sendNotification(data: NotificationCreatePayload): Promise<{ id: number; recipient_count: number }> {
  const response = await api.post('/notifications', data)
  return response.data.data
}

export async function markNotificationRead(id: number): Promise<void> {
  await api.post(`/notifications/${id}/read`)
}

export async function markAllNotificationsRead(): Promise<void> {
  await api.post('/notifications/read-all')
}
