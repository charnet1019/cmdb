type SystemNotificationPayload = {
  id?: number | string
  receipt_id?: number | string
  title?: string
  content?: string
  sender?: {
    username?: string
    full_name?: string | null
  } | null
}

export const OPEN_NOTIFICATIONS_PANEL_EVENT = 'notifications:open-panel'

export function isSystemNotificationSupported() {
  return typeof window !== 'undefined' && 'Notification' in window
}

export async function requestSystemNotificationPermission(): Promise<NotificationPermission> {
  if (!isSystemNotificationSupported()) return 'denied'
  if (Notification.permission !== 'default') return Notification.permission
  return await Notification.requestPermission()
}

function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) return value
  return `${value.slice(0, maxLength - 1)}...`
}

export function showSystemNotification(data: SystemNotificationPayload) {
  if (!isSystemNotificationSupported() || Notification.permission !== 'granted') return false

  const senderName = data.sender?.full_name || data.sender?.username || '系统'
  const content = data.content?.trim() || '你收到了一条新的站内信'
  const notification = new Notification(data.title?.trim() || '新站内信', {
    body: truncateText(`${senderName}: ${content}`, 180),
    tag: `cmdb-notification-${data.receipt_id || data.id || Date.now()}`,
  })

  notification.onclick = () => {
    window.focus()
    window.dispatchEvent(new CustomEvent(OPEN_NOTIFICATIONS_PANEL_EVENT))
    notification.close()
  }

  return true
}
