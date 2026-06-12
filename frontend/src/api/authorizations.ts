import { api } from './index'
import type { Authorization } from '@/types'

export interface AuthorizationCreate {
  entity_type: 'user' | 'group'
  entity_id: number
  target_type: 'asset' | 'organization'
  target_ids: string[]
  permissions: string[]
  valid_from?: string
  valid_until?: string
}

// Get authorizations list
export async function getAuthorizations(params: {
  page?: number
  limit?: number
  entity_type?: string
  target_type?: string
  is_active?: boolean
}) {
  const response = await api.get('/authorizations', { params })
  return {
    items: response.data.data || [],
    total: response.data.meta?.total || 0
  }
}

// Create authorization
export async function createAuthorization(data: AuthorizationCreate): Promise<Authorization> {
  const response = await api.post('/authorizations', data)
  return response.data.data
}

// Update authorization
export async function updateAuthorization(id: number, data: Partial<AuthorizationCreate & { is_active: boolean }>): Promise<Authorization> {
  const response = await api.put(`/authorizations/${id}`, data)
  return response.data.data
}

// Delete authorization
export async function deleteAuthorization(id: number): Promise<void> {
  await api.delete(`/authorizations/${id}`)
}

// Get users for selection
export async function getUsersForAuth(): Promise<Array<{ id: number; name: string; full_name: string | null }>> {
  const response = await api.get('/authorizations/users')
  return response.data.data
}

// Get groups for selection
export async function getGroupsForAuth(): Promise<Array<{ id: number; name: string }>> {
  const response = await api.get('/authorizations/groups')
  return response.data.data
}

// Get assets for selection
export async function getAssetsForAuth(): Promise<Array<{ id: string; name: string; category: string; internal_address: string | null; external_address: string | null; organization_id: number | null }>> {
  const response = await api.get('/authorizations/assets')
  return response.data.data
}

// Get organizations for selection
export async function getOrganizationsForAuth(): Promise<Array<{ id: number; name: string; path: string | null; name_path: string }>> {
  const response = await api.get('/authorizations/organizations')
  return response.data.data
}