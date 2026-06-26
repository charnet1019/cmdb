import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserSimple } from '@/types'
import { login as loginApi, logout as logoutApi, getCurrentUser, heartbeat as heartbeatApi } from '@/api/auth'

const HEARTBEAT_INTERVAL_MS = 2 * 60 * 1000  // 2 minutes

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserSimple | null>(null)
  const permissions = ref<string[]>([])
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
    token.value = response.access_token
    user.value = response.user
    permissions.value = response.user.permissions ?? []
    localStorage.setItem('token', response.access_token)
    startHeartbeat()
    return response
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
    isAuthenticated,
    isSuperuser,
    username,
    login,
    logout,
    fetchUser,
    hasPermission,
    hasAnyPermission
  }
})