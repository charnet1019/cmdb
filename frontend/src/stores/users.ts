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
  const usersLimit = ref(20)
  const groupsPage = ref(1)
  const groupsLimit = ref(20)

  // Actions
  async function fetchUsers(page?: number, limit?: number, search?: string, isActive?: boolean) {
    if (page !== undefined) usersPage.value = page
    if (limit !== undefined) usersLimit.value = limit
    const result = await getUsers({
      page: usersPage.value,
      limit: usersLimit.value,
      search: search || undefined,
      is_active: isActive ?? undefined,
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

  async function fetchGroups(page?: number, limit?: number, search?: string) {
    if (page !== undefined) groupsPage.value = page
    if (limit !== undefined) groupsLimit.value = limit
    const result = await getGroups({
      page: groupsPage.value,
      limit: groupsLimit.value,
      search: search || undefined,
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
