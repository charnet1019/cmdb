import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserSimple, TokenResponse, MFARequiredData, MustChangePasswordData } from '@/types'
import { login as loginApi, logout as logoutApi, getCurrentUser, heartbeat as heartbeatApi, loginMFAVerify, forceChangePassword as forceChangePasswordApi } from '@/api/auth'
import { clearPendingSessionActivity, hasPendingSessionActivity, markSessionActivity, USER_ACTIVITY_EVENTS } from '@/utils/sessionActivity'

const HEARTBEAT_INTERVAL_MS = 2 * 60 * 1000  // 2 minutes
const ACTIVITY_HEARTBEAT_THROTTLE_MS = 30 * 1000
const SESSION_EXPIRED_MESSAGE = '登录已超时，请重新登录'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(null)
  const user = ref<UserSimple | null>(null)
  const permissions = ref<string[]>([])
  const pendingMFAChallengeToken = ref<string | null>(null)
  const pendingMFASetup = ref(false)  // true = first-time binding flow
  const pendingForceChangeChallengeToken = ref<string | null>(null)
  const sessionExpiresAt = ref<string | null>(null)
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let sessionExpiryTimer: ReturnType<typeof setTimeout> | null = null
  let eventSource: EventSource | null = null
  let userActivitySinceHeartbeat = false
  let heartbeatInFlight: Promise<void> | null = null
  let sessionExpiryConfirmation: Promise<boolean> | null = null
  let lastActivityHeartbeatAt = 0

  function isSessionActive() {
    return !!token.value || !!user.value
  }

  async function sendHeartbeat(userActive = false) {
    if (!isSessionActive()) return
    if (hasSessionExpired()) {
      void handleSessionExpired()
      return
    }

    const shouldExtend = userActive || userActivitySinceHeartbeat
    try {
      const response = await heartbeatApi(shouldExtend)
      if (shouldExtend) {
        userActivitySinceHeartbeat = false
        clearPendingSessionActivity()
      }
      if (response.expires_at) setSessionExpiresAt(response.expires_at)
    } catch (error: any) {
      const status = error?.response?.status
      if (status === 401 || status === 403) {
        void handleSessionExpired()
      }
      // Transient network errors are left to the next heartbeat/API call.
    }
  }

  function queueHeartbeat(userActive = false) {
    if (userActive) userActivitySinceHeartbeat = true
    if (heartbeatInFlight) return
    heartbeatInFlight = sendHeartbeat(userActive).finally(() => {
      heartbeatInFlight = null
      if (userActivitySinceHeartbeat && isSessionActive() && !hasSessionExpired()) {
        queueHeartbeat(false)
      }
    })
  }

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      queueHeartbeat(false)
    }, HEARTBEAT_INTERVAL_MS)
  }

  function stopHeartbeat() {
    if (heartbeatTimer !== null) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function parseSessionExpiresAt(value: string | null | undefined): number | null {
    if (!value) return null
    const timestamp = Date.parse(value)
    return Number.isFinite(timestamp) ? timestamp : null
  }

  function clearSessionExpiryTimer() {
    if (sessionExpiryTimer !== null) {
      clearTimeout(sessionExpiryTimer)
      sessionExpiryTimer = null
    }
  }

  function hasSessionExpired(): boolean {
    const expiresAtMs = parseSessionExpiresAt(sessionExpiresAt.value)
    return expiresAtMs !== null && Date.now() >= expiresAtMs
  }

  async function confirmActiveSessionBeforeLogout(): Promise<boolean> {
    const shouldTryRenewal = userActivitySinceHeartbeat || hasPendingSessionActivity()
    if (!shouldTryRenewal) return false
    if (sessionExpiryConfirmation) return sessionExpiryConfirmation

    sessionExpiryConfirmation = heartbeatApi(true)
      .then((response) => {
        userActivitySinceHeartbeat = false
        clearPendingSessionActivity()
        if (response.expires_at) {
          setSessionExpiresAt(response.expires_at)
          return !hasSessionExpired()
        }
        return false
      })
      .catch(() => false)
      .finally(() => {
        sessionExpiryConfirmation = null
      })

    return sessionExpiryConfirmation
  }

  function expireSessionAndRedirect() {
    if (!token.value && !user.value) return
    handleTokenCleared()
    sessionStorage.setItem("auth:logout-message", SESSION_EXPIRED_MESSAGE)
    if (window.location.pathname !== "/login") {
      window.location.href = "/login"
    }
  }

  async function handleSessionExpired() {
    if (!token.value && !user.value) return
    if (await confirmActiveSessionBeforeLogout()) return
    expireSessionAndRedirect()
  }

  function scheduleSessionExpiryTimer() {
    clearSessionExpiryTimer()
    const expiresAtMs = parseSessionExpiresAt(sessionExpiresAt.value)
    if (expiresAtMs === null) return

    const delayMs = expiresAtMs - Date.now()
    if (delayMs <= 0) {
      void handleSessionExpired()
      return
    }
    sessionExpiryTimer = setTimeout(() => {
      void handleSessionExpired()
    }, delayMs)
  }

  function setSessionExpiresAt(expiresAt: string | null | undefined) {
    sessionExpiresAt.value = expiresAt || null
    scheduleSessionExpiryTimer()
  }

  function checkSessionExpiry() {
    if (hasSessionExpired()) {
      void handleSessionExpired()
    }
  }

  function handleVisibilityChange() {
    if (!document.hidden) {
      checkSessionExpiry()
    }
  }

  function markUserActivity() {
    if (!isSessionActive()) return
    markSessionActivity()
    userActivitySinceHeartbeat = true

    const expiresAtMs = parseSessionExpiresAt(sessionExpiresAt.value)
    const now = Date.now()
    if (
      expiresAtMs !== null &&
      expiresAtMs - now <= HEARTBEAT_INTERVAL_MS &&
      now - lastActivityHeartbeatAt >= ACTIVITY_HEARTBEAT_THROTTLE_MS
    ) {
      lastActivityHeartbeatAt = now
      queueHeartbeat(true)
    }
  }

  function addUserActivityListeners() {
    USER_ACTIVITY_EVENTS.forEach(eventName => {
      window.removeEventListener(eventName, markUserActivity)
      window.addEventListener(eventName, markUserActivity, { passive: true })
    })
  }

  function removeUserActivityListeners() {
    USER_ACTIVITY_EVENTS.forEach(eventName => {
      window.removeEventListener(eventName, markUserActivity)
    })
    userActivitySinceHeartbeat = false
    clearPendingSessionActivity()
    lastActivityHeartbeatAt = 0
  }

  function disconnectEventStream() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  }

  function connectEventStream() {
    if (eventSource || !token.value) return

    eventSource = new EventSource("/api/v1/events/stream", { withCredentials: true })
    eventSource.addEventListener("force_logout", (event) => {
      let message = "账号已被管理员强制离线"
      try {
        const data = JSON.parse((event as MessageEvent).data || "{}")
        message = data.message || message
      } catch {
        // Keep default message.
      }
      disconnectEventStream()
      handleTokenCleared()
      sessionStorage.setItem("auth:logout-message", message)
      if (window.location.pathname !== "/login") {
        window.location.href = "/login"
      }
    })
    eventSource.addEventListener("notification", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data || "{}")
        void import("@/stores/notifications").then(({ useNotificationsStore }) => {
          useNotificationsStore().handleRealtimeNotification(data)
        })
      } catch {
        // Ignore malformed realtime payloads.
      }
    })
  }

  function initializeAuthenticatedSession(expiresAt?: string | null) {
    if (expiresAt !== undefined) {
      setSessionExpiresAt(expiresAt)
    } else {
      scheduleSessionExpiryTimer()
    }
    addUserActivityListeners()
    startHeartbeat()
    connectEventStream()
    void import("@/stores/notifications").then(({ useNotificationsStore }) => {
      const notificationStore = useNotificationsStore()
      void notificationStore.fetchUnreadCount()
      void notificationStore.fetchCanSend()
    }).catch(() => {})
  }

  function handleSessionExtended(event: Event) {
    if (!isSessionActive()) return
    const expiresAt = (event as CustomEvent<{ expiresAt?: string | null }>).detail?.expiresAt
    if (!expiresAt) return
    userActivitySinceHeartbeat = false
    clearPendingSessionActivity()
    setSessionExpiresAt(expiresAt)
  }

  // Listen for token cleared event from API interceptor
  const handleTokenCleared = () => {
    stopHeartbeat()
    clearSessionExpiryTimer()
    removeUserActivityListeners()
    disconnectEventStream()
    sessionExpiresAt.value = null
    token.value = null
    user.value = null
    permissions.value = []
    pendingMFAChallengeToken.value = null
    pendingMFASetup.value = false
    pendingForceChangeChallengeToken.value = null
    void import("@/stores/notifications").then(({ useNotificationsStore }) => {
      useNotificationsStore().reset()
    }).catch(() => {})
  }

  // Remove any existing listener first (prevents accumulation during HMR)
  window.removeEventListener('auth:token-cleared', handleTokenCleared)
  window.addEventListener('auth:token-cleared', handleTokenCleared)
  window.removeEventListener('auth:session-extended', handleSessionExtended)
  window.addEventListener('auth:session-extended', handleSessionExtended)
  window.removeEventListener('focus', checkSessionExpiry)
  window.addEventListener('focus', checkSessionExpiry)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  document.addEventListener('visibilitychange', handleVisibilityChange)

  // Getters
  const isAuthenticated = computed(() => !!user.value || !!token.value)
  const isSuperuser = computed(() => user.value?.is_superuser ?? false)
  const username = computed(() => user.value?.username || '')

  // Actions
  async function login(username: string, password: string, remember: boolean = false) {
    const response = await loginApi({ username, password, remember })

    // Check if must change password
    if ((response as MustChangePasswordData).must_change_password) {
      const mcpResponse = response as MustChangePasswordData
      pendingMFAChallengeToken.value = null
      pendingMFASetup.value = false
      pendingForceChangeChallengeToken.value = mcpResponse.challenge_token
      return response
    }

    // Check if MFA is required
    if ((response as MFARequiredData).requires_mfa) {
      const mfaResponse = response as MFARequiredData
      pendingForceChangeChallengeToken.value = null
      pendingMFAChallengeToken.value = mfaResponse.challenge_token
      pendingMFASetup.value = mfaResponse.setup ?? false
      return response
    }

    const tokenResponse = response as TokenResponse
    token.value = 'cookie-session'
    user.value = tokenResponse.user
    permissions.value = tokenResponse.user.permissions ?? []
    initializeAuthenticatedSession(tokenResponse.expires_at)
    return tokenResponse
  }

  async function verifyMFA(code: string, isSetup: boolean = false) {
    const challengeToken = pendingMFAChallengeToken.value
    if (!challengeToken) {
      throw new Error('No pending MFA verification')
    }

    const tokenResponse = await loginMFAVerify(challengeToken, code, isSetup)
    pendingMFAChallengeToken.value = null
    pendingMFASetup.value = false
    token.value = 'cookie-session'
    user.value = tokenResponse.user
    permissions.value = tokenResponse.user.permissions ?? []
    initializeAuthenticatedSession(tokenResponse.expires_at)
    return tokenResponse
  }

  function clearPendingMFA() {
    pendingMFAChallengeToken.value = null
    pendingMFASetup.value = false
  }

  async function forceChangePassword(newPassword: string, confirmPassword: string) {
    const challengeToken = pendingForceChangeChallengeToken.value
    if (!challengeToken) {
      throw new Error('No pending force change password')
    }

    const response = await forceChangePasswordApi({
      challenge_token: challengeToken,
      new_password: newPassword,
      confirm_password: confirmPassword,
    })
    pendingForceChangeChallengeToken.value = null

    if ((response as MFARequiredData).requires_mfa) {
      const mfaResponse = response as MFARequiredData
      pendingMFAChallengeToken.value = mfaResponse.challenge_token
      pendingMFASetup.value = mfaResponse.setup ?? false
      return response
    }

    const tokenResponse = response as TokenResponse
    token.value = 'cookie-session'
    user.value = tokenResponse.user
    permissions.value = tokenResponse.user.permissions ?? []
    initializeAuthenticatedSession(tokenResponse.expires_at)
    return tokenResponse
  }

  function clearPendingForceChange() {
    pendingForceChangeChallengeToken.value = null
  }

  async function logout() {
    stopHeartbeat()
    try {
      await logoutApi()
    } catch (e) {
      // Ignore logout errors
    } finally {
      handleTokenCleared()
    }
  }

  async function fetchUser() {
    try {
      const userData = await getCurrentUser()
      token.value = 'cookie-session'
      user.value = userData
      permissions.value = userData.permissions ?? []
      // Re-establish presence — Redis key may have expired while away
      const heartbeat = await heartbeatApi(false)
      initializeAuthenticatedSession(heartbeat.expires_at ?? userData.session_expires_at ?? null)
      return userData
    } catch (e) {
      logout()
      throw e
    }
  }

  function hasPermission(permission: string): boolean {
    if (user.value?.is_superuser) return true
    return permissions.value.includes(permission)
  }

  function hasAnyPermission(perms: string[]): boolean {
    return perms.some(p => hasPermission(p))
  }


  function updateSessionExpiresAt(expiresAt: string | null | undefined) {
    setSessionExpiresAt(expiresAt)
  }

  return {
    token,
    user,
    permissions,
    pendingMFAChallengeToken,
    pendingMFASetup,
    pendingForceChangeChallengeToken,
    isAuthenticated,
    isSuperuser,
    username,
    login,
    verifyMFA,
    clearPendingMFA,
    forceChangePassword,
    clearPendingForceChange,
    logout,
    fetchUser,
    hasPermission,
    hasAnyPermission,
    updateSessionExpiresAt
  }
})