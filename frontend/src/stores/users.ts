import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User, Group } from '@/types'
import { getUsers, getGroups } from '@/api/users'

export const useUsersStore = defineStore('users', () => {
  // State
  const users = ref<User[]>([])
  const groups = ref<Group[]>([])
  const allUsers = ref<User[]>([])
  const usersTotal = ref(0)
  const groupsTotal = ref(0)
  const usersPage = ref(1)
  const usersLimit = ref(15)
  const groupsPage = ref(1)
  const groupsLimit = ref(15)

  // Actions
  async function fetchUsers(params?: { page?: number; limit?: number; search?: string; is_active?: boolean }) {
    if (params?.page !== undefined) usersPage.value = params.page
    if (params?.limit !== undefined) usersLimit.value = params.limit
    const result = await getUsers({
      page: params?.page ?? usersPage.value,
      limit: params?.limit ?? usersLimit.value,
      search: params?.search || undefined,
      is_active: params?.is_active ?? undefined,
    })
    users.value = result.items || []
    usersTotal.value = result.total || 0
    return result
  }

  async function fetchAllUsers() {
    const result = await getUsers({ limit: 100 })
    allUsers.value = result.items || []
    return allUsers.value
  }

  async function fetchGroups(params?: { page?: number; limit?: number; search?: string }) {
    if (params?.page !== undefined) groupsPage.value = params.page
    if (params?.limit !== undefined) groupsLimit.value = params.limit
    const result = await getGroups({
      page: params?.page ?? groupsPage.value,
      limit: params?.limit ?? groupsLimit.value,
      search: params?.search || undefined,
    })
    groups.value = result.items || []
    groupsTotal.value = result.total || 0
    return result
  }

  async function fetchAllGroups() {
    const result = await getGroups({ limit: 100 })
    groups.value = result.items || []
    return groups.value
  }

  function resetUsers() {
    users.value = []
    usersTotal.value = 0
    usersPage.value = 1
  }

  function resetGroups() {
    groups.value = []
    groupsTotal.value = 0
    groupsPage.value = 1
  }

  return {
    users,
    groups,
    allUsers,
    usersTotal,
    groupsTotal,
    usersPage,
    usersLimit,
    groupsPage,
    groupsLimit,
    fetchUsers,
    fetchAllUsers,
    fetchGroups,
    fetchAllGroups,
    resetUsers,
    resetGroups,
  }
})
