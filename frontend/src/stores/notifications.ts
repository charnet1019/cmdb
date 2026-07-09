import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { NotificationItem, NotificationCreatePayload } from '@/types'
import {
  getNotifications,
  getUnreadCount,
  getCanSendNotification,
  sendNotification as sendNotificationApi,
  markNotificationRead,
  markAllNotificationsRead,
} from '@/api/notifications'

export const useNotificationsStore = defineStore('notifications', () => {
  const items = ref<NotificationItem[]>([])
  const unreadCount = ref(0)
  const canSend = ref(false)
  const loading = ref(false)
  const sending = ref(false)

  async function fetchUnreadCount() {
    unreadCount.value = await getUnreadCount()
    return unreadCount.value
  }

  async function fetchCanSend() {
    canSend.value = await getCanSendNotification()
    return canSend.value
  }

  async function fetchNotifications(status: 'all' | 'unread' | 'read' = 'all') {
    loading.value = true
    try {
      const response = await getNotifications({ status, page: 1, limit: 20 })
      items.value = response.items
      return response
    } finally {
      loading.value = false
    }
  }

  async function sendNotification(data: NotificationCreatePayload) {
    sending.value = true
    try {
      return await sendNotificationApi(data)
    } finally {
      sending.value = false
    }
  }

  async function markRead(item: NotificationItem) {
    if (item.read_at) return
    await markNotificationRead(item.id)
    item.read_at = new Date().toISOString()
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  }

  async function markAllRead() {
    await markAllNotificationsRead()
    const now = new Date().toISOString()
    items.value.forEach(item => {
      if (!item.read_at) item.read_at = now
    })
    unreadCount.value = 0
  }

  function handleRealtimeNotification(data: any) {
    unreadCount.value += 1
    if (!data?.id) return
    items.value.unshift({
      id: data.receipt_id || data.id,
      notification_id: data.id,
      title: data.title || '新站内信',
      content: data.content || '',
      sender: data.sender || null,
      read_at: null,
      created_at: data.created_at || new Date().toISOString(),
    })
    items.value = items.value.slice(0, 20)
  }

  function reset() {
    items.value = []
    unreadCount.value = 0
    canSend.value = false
    loading.value = false
    sending.value = false
  }

  return {
    items,
    unreadCount,
    canSend,
    loading,
    sending,
    fetchUnreadCount,
    fetchCanSend,
    fetchNotifications,
    sendNotification,
    markRead,
    markAllRead,
    handleRealtimeNotification,
    reset,
  }
})
