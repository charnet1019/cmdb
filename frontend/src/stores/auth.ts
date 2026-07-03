import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserSimple, MFARequiredData } from '@/types'
import { login as loginApi, logout as logoutApi, getCurrentUser, heartbeat as heartbeatApi, loginMFAVerify } from '@/api/auth'

const HEARTBEAT_INTERVAL_MS = 2 * 60 * 1000  // 2 minutes

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserSimple | null>(null)
  const permissions = ref<string[]>([])
  const pendingMFAUserId = ref<number | null>(null)
  const pendingMFASetup = ref(false)  // true = first-time binding flow
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null

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

  // Listen for token cleared event from API interceptor
  const handleTokenCleared = () => {
    stopHeartbeat()
    token.value = null
    user.value = null
    permissions.value = []
    pendingMFAUserId.value = null
    pendingMFASetup.value = false
  }

  // Remove any existing listener first (prevents accumulation during HMR)
  window.removeEventListener('auth:token-cleared', handleTokenCleared)
  window.addEventListener('auth:token-cleared', handleTokenCleared)

  // Getters
  const isAuthenticated = computed(() => !!token.value)
  const isSuperuser = computed(() => user.value?.is_superuser ?? false)
  const username = computed(() => user.value?.username || '')

  // Actions
  async function login(username: string, password: string, remember: boolean = false) {
    const response = await loginApi({ username, password, remember })

    // Check if MFA is required
    if ((response as MFARequiredData).requires_mfa) {
      const mfaResponse = response as MFARequiredData
      pendingMFAUserId.value = mfaResponse.user_id
      pendingMFASetup.value = mfaResponse.setup ?? false
      return response
    }

    const tokenResponse = response as any
    token.value = tokenResponse.access_token
    user.value = tokenResponse.user
    permissions.value = tokenResponse.user.permissions ?? []
    localStorage.setItem('token', tokenResponse.access_token)
    startHeartbeat()
    return tokenResponse
  }

  async function verifyMFA(code: string, isSetup: boolean = false) {
    const userId = pendingMFAUserId.value
    if (!userId) {
      throw new Error('No pending MFA verification')
    }

    const tokenResponse = await loginMFAVerify(userId, code, isSetup)
    pendingMFAUserId.value = null
    pendingMFASetup.value = false
    token.value = tokenResponse.access_token
    user.value = tokenResponse.user
    permissions.value = tokenResponse.user.permissions ?? []
    localStorage.setItem('token', tokenResponse.access_token)
    startHeartbeat()
    return tokenResponse
  }

  function clearPendingMFA() {
    pendingMFAUserId.value = null
    pendingMFASetup.value = false
  }

  async function logout() {
    stopHeartbeat()
    try {
      await logoutApi()
    } catch (e) {
      // Ignore logout errors
    } finally {
      token.value = null
      user.value = null
      permissions.value = []
      localStorage.removeItem('token')
    }
  }

  async function fetchUser() {
    if (!token.value) return null
    try {
      const userData = await getCurrentUser()
      user.value = userData
      permissions.value = userData.permissions ?? []
      // Re-establish presence — Redis key may have expired while away
      await heartbeatApi()
      startHeartbeat()
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
    pendingMFAUserId,
    pendingMFASetup,
    isAuthenticated,
    isSuperuser,
    username,
    login,
    verifyMFA,
    clearPendingMFA,
    logout,
    fetchUser,
    hasPermission,
    hasAnyPermission
  }
})