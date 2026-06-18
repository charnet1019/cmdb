import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserSimple } from '@/types'
import { login as loginApi, logout as logoutApi, getCurrentUser } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserSimple | null>(null)
  const permissions = ref<string[]>([])

  // Listen for token cleared event from API interceptor
  const handleTokenCleared = () => {
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
    return response
  }

  async function logout() {
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