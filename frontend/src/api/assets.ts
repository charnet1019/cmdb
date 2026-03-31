import { getPaginated, api } from './index'
import type { Asset, AssetCategory, Credential, Organization } from '@/types'

// Asset APIs
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
  return response.data.data
}

export async function createAsset(data: Partial<Asset>): Promise<Asset> {
  const response = await api.post('/assets', data)
  return response.data.data
}

export async function updateAsset(id: number, data: Partial<Asset>): Promise<Asset> {
  const response = await api.put(`/assets/${id}`, data)
  return response.data.data
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
  return response.data.data
}

export async function decryptCredential(credentialId: number): Promise<Credential> {
  const response = await api.post(`/credentials/${credentialId}/decrypt`)
  return response.data.data
}

export async function deleteCredential(id: number): Promise<void> {
  await api.delete(`/credentials/${id}`)
}