import { getPaginated, api } from './index'
import type { Asset, AssetCategory, Credential, Organization } from '@/types'

// Asset statistics type
export interface AssetStats {
  total: number
  by_category: Record<string, number>
  by_platform: Record<string, number>
  by_device_type: Record<string, number>
}

// Asset APIs
export async function getAssetStats(): Promise<AssetStats> {
  const response = await api.get('/assets/stats')
  return response.data.data
}

export async function getAssets(params: {
  page?: number
  limit?: number
  category?: AssetCategory
  organization_id?: number
  search?: string
  is_active?: boolean
}) {
  return getPaginated<Asset>('/assets', params)
}

export async function getAsset(id: number): Promise<Asset> {
  const response = await api.get(`/assets/${id}`)
  // Backend returns AssetResponse directly
  return response.data
}

export async function createAsset(data: Partial<Asset>): Promise<Asset> {
  const response = await api.post('/assets', data)
  // Backend returns AssetResponse directly, not wrapped in { data: ... }
  return response.data
}

export async function updateAsset(id: number, data: Partial<Asset>): Promise<Asset> {
  const response = await api.put(`/assets/${id}`, data)
  // Backend returns AssetResponse directly
  return response.data
}

export async function deleteAsset(id: number): Promise<void> {
  await api.delete(`/assets/${id}`)
}

// Organization APIs
export async function getOrganizations(): Promise<Organization[]> {
  const response = await api.get('/organizations')
  return response.data.data
}

export async function createOrganization(name: string, parentId?: number): Promise<Organization> {
  const response = await api.post('/organizations', null, {
    params: { name, parent_id: parentId }
  })
  return response.data.data
}

// Credential APIs
export async function getCredentials(assetId?: number): Promise<Credential[]> {
  const response = await api.get('/credentials', {
    params: { asset_id: assetId }
  })
  return response.data.data
}

export async function createCredential(assetId: number, data: {
  username: string
  password: string
  credential_type?: string
  metadata?: Record<string, any>
}): Promise<Credential> {
  const response = await api.post('/credentials', data, {
    params: { asset_id: assetId }
  })
  // Backend returns CredentialResponse directly
  return response.data
}

export async function updateCredential(credentialId: number, data: {
  username?: string
  password?: string
  metadata?: Record<string, any>
}): Promise<Credential> {
  const response = await api.put(`/credentials/${credentialId}`, data)
  // Backend returns CredentialResponse directly
  return response.data
}

export async function decryptCredential(credentialId: number): Promise<Credential> {
  const response = await api.post(`/credentials/${credentialId}/decrypt`)
  // Backend returns CredentialDecryptResponse directly
  return response.data
}

export async function deleteCredential(id: number): Promise<void> {
  await api.delete(`/credentials/${id}`)
}