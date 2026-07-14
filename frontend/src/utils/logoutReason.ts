export type LogoutReason =
  | 'local_idle_timeout'
  | 'server_session_invalid'
  | 'heartbeat_session_invalid'
  | 'renewal_failed'
  | 'user_disabled'
  | 'admin_forced'

const LOGOUT_MESSAGE_KEY = 'auth:logout-message'

export const LOGOUT_MESSAGES: Record<LogoutReason, string> = {
  local_idle_timeout: '由于长时间未操作，登录已超时，请重新登录',
  server_session_invalid: '登录会话已失效，请重新登录',
  heartbeat_session_invalid: '会话心跳校验失败，请重新登录',
  renewal_failed: '会话续期失败，请重新登录',
  user_disabled: '账号已被管理员禁用，请联系管理员',
  admin_forced: '账号已被管理员强制离线',
}

export function getLogoutMessage(reason: LogoutReason, fallback?: string | null): string {
  return fallback || LOGOUT_MESSAGES[reason]
}

export function setLogoutMessage(reason: LogoutReason, fallback?: string | null) {
  sessionStorage.setItem(LOGOUT_MESSAGE_KEY, getLogoutMessage(reason, fallback))
}

export function consumeLogoutMessage(): string | null {
  const stored = sessionStorage.getItem(LOGOUT_MESSAGE_KEY)
  if (stored) sessionStorage.removeItem(LOGOUT_MESSAGE_KEY)
  return stored
}

export function resolveLogoutReason(status?: number, detail?: string): LogoutReason | null {
  if (status === 403 && detail === '用户已被禁用') return 'user_disabled'
  if (status === 401) return 'server_session_invalid'
  return null
}
