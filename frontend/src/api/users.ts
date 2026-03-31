import { getPaginated, api } from './index'
import type { User, Group } from '@/types'

// User APIs
export async function getUsers(params: {
  page?: number
  limit?: number
  search?: string
  is_active?: boolean
}) {
  return getPaginated<User>('/users', params)
}

export async function getUser(id: number): Promise<User> {
  const response = await api.get(`/users/${id}`)
  return response.data.data
}

export async function createUser(data: {
  username: string
  email: string
  password: string
  full_name?: string
  phone?: string
  group_ids?: number[]
  is_active?: boolean
  mfa_enabled?: boolean
}): Promise<User> {
  const response = await api.post('/users', data)
  return response.data.data
}

export async function updateUser(id: number, data: Partial<User> & { group_ids?: number[] }): Promise<User> {
  const response = await api.put(`/users/${id}`, data)
  return response.data.data
}

export async function deleteUser(id: number): Promise<void> {
  await api.delete(`/users/${id}`)
}

export async function resetUserPassword(id: number, data: {
  method?: 'auto' | 'manual'
  new_password?: string
  force_change?: boolean
  send_email?: boolean
}): Promise<{ temp_password?: string }> {
  const response = await api.post(`/users/${id}/reset-password`, data)
  return response.data.data
}

// User Authorizations API
export interface UserAuthorization {
  id: number
  asset_id: number
  asset_name: string
  asset_category: string
  permissions: string[]
  valid_until: string | null
  status: string
  source_type: 'direct' | 'group'
  group_id?: number
  group_name?: string
}

export interface UserAuthorizationsResponse {
  direct: UserAuthorization[]
  inherited: UserAuthorization[]
  total: number
}

export async function getUserAuthorizations(userId: number): Promise<UserAuthorizationsResponse> {
  const response = await api.get(`/users/${userId}/authorizations`)
  return response.data.data
}

// Group APIs
export async function getGroups(params: {
  page?: number
  limit?: number
  search?: string
}) {
  return getPaginated<Group>('/groups', params)
}

export async function createGroup(data: {
  name: string
  description?: string
  initial_member_ids?: number[]
}): Promise<Group> {
  const response = await api.post('/groups', data)
  return response.data.data
}

export async function deleteGroup(id: number): Promise<void> {
  await api.delete(`/groups/${id}`)
}

// Group Authorizations API
export interface GroupAuthorization {
  id: number
  asset_id: number
  asset_name: string
  asset_category: string
  permissions: string[]
  valid_until: string | null
  status: string
}

export async function getGroupAuthorizations(groupId: number): Promise<GroupAuthorization[]> {
  const response = await api.get(`/groups/${groupId}/authorizations`)
  return response.data.data
}

// Group Members API
export interface GroupMember {
  id: number
  username: string
  full_name: string | null
  email: string
  is_active: boolean
}

export async function getGroupMembers(groupId: number): Promise<GroupMember[]> {
  const response = await api.get(`/groups/${groupId}/members`)
  return response.data.data
}

export async function addGroupMembers(groupId: number, userIds: number[]): Promise<void> {
  await api.post(`/groups/${groupId}/members`, userIds)
}

export async function removeGroupMember(groupId: number, userId: number): Promise<void> {
  await api.delete(`/groups/${groupId}/members/${userId}`)
}

export async function updateGroup(id: number, data: { name?: string; description?: string }): Promise<Group> {
  const response = await api.put(`/groups/${id}`, null, { params: data })
  return response.data.data
}