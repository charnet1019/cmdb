import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserSimple, MFARequiredData, MustChangePasswordData } from '@/types'
import { login as loginApi, logout as logoutApi, getCurrentUser, heartbeat as heartbeatApi, loginMFAVerify, forceChangePassword as forceChangePasswordApi } from '@/api/auth'

const HEARTBEAT_INTERVAL_MS = 2 * 60 * 1000  // 2 minutes

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(null)
  const user = ref<UserSimple | null>(null)
  const permissions = ref<string[]>([])
  const pendingMFAChallengeToken = ref<string | null>(null)
  const pendingMFASetup = ref(false)  // true = first-time binding flow
  const pendingForceChangeChallengeToken = ref<string | null>(null)
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let eventSource: EventSource | null = null

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = setInterval(async () => {
      try {
        await heartbeatApi()
      } catch {
        // Heartbeat failure is silent — next API call will 401 if token expired
      }
    }, HEARTBEAT_INTERVAL_MS)
  }

  function stopHeartbeat() {
    if (heartbeatTimer !== null) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
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

  function initializeAuthenticatedSession() {
    startHeartbeat()
    connectEventStream()
    void import("@/stores/notifications").then(({ useNotificationsStore }) => {
      const notificationStore = useNotificationsStore()
      void notificationStore.fetchUnreadCount()
      void notificationStore.fetchCanSend()
    }).catch(() => {})
  }

  // Listen for token cleared event from API interceptor
  const handleTokenCleared = () => {
    stopHeartbeat()
    disconnectEventStream()
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

    const tokenResponse = response as any
    token.value = 'cookie-session'
    user.value = tokenResponse.user
    permissions.value = tokenResponse.user.permissions ?? []
    initializeAuthenticatedSession()
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
    initializeAuthenticatedSession()
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

    const tokenResponse = response as any
    token.value = 'cookie-session'
    user.value = tokenResponse.user
    permissions.value = tokenResponse.user.permissions ?? []
    initializeAuthenticatedSession()
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
      await heartbeatApi()
      initializeAuthenticatedSession()
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
    hasAnyPermission
  }
})