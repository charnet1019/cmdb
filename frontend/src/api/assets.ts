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

export async function getAsset(id: string): Promise<Asset> {
  const response = await api.get(`/assets/${id}`)
  // Backend returns AssetResponse directly
  return response.data
}

export async function createAsset(data: Partial<Asset>): Promise<Asset> {
  const response = await api.post('/assets', data)
  // Backend returns AssetResponse directly, not wrapped in { data: ... }
  return response.data
}

export async function updateAsset(id: string, data: Partial<Asset>): Promise<Asset> {
  const response = await api.put(`/assets/${id}`, data)
  // Backend returns AssetResponse directly
  return response.data
}

export async function deleteAsset(id: string): Promise<void> {
  await api.delete(`/assets/${id}`)
}

// Bulk operations
export async function bulkUpdateAssets(ids: string[], data: Partial<Asset>): Promise<void> {
  await api.put('/assets/bulk', { ids, data })
}

export async function bulkDeleteAssets(ids: string[]): Promise<void> {
  await api.delete('/assets/bulk', { data: { ids } })
}

// Organization APIs
export interface OrganizationResponse {
  organizations: Organization[]
  root_asset_count: number
  total_assets: number
}

export async function getOrganizations(): Promise<Organization[]> {
  const response = await api.get('/organizations')
  return response.data.data
}

export async function getOrganizationsWithStats(): Promise<OrganizationResponse> {
  const response = await api.get('/organizations')
  return {
    organizations: response.data.data,
    root_asset_count: response.data.root_asset_count || 0,
    total_assets: response.data.total_assets || 0
  }
}

export async function createOrganization(name: string, parentId?: number): Promise<Organization> {
  const response = await api.post('/organizations', null, {
    params: { name, parent_id: parentId }
  })
  return response.data.data
}

export async function updateOrganization(orgId: number, name: string): Promise<Organization> {
  const response = await api.put(`/organizations/${orgId}`, null, {
    params: { name }
  })
  return response.data.data
}

export async function deleteOrganization(orgId: number): Promise<void> {
  await api.delete(`/organizations/${orgId}`)
}

export async function reorderOrganizations(parentId: number | null, orderedIds: number[]): Promise<void> {
  await api.post('/organizations/reorder', {
    parent_id: parentId,
    ordered_ids: orderedIds
  })
}

// Credential APIs
export async function getCredentials(assetId?: string): Promise<Credential[]> {
  const response = await api.get('/credentials', {
    params: { asset_id: assetId }
  })
  return response.data.data
}

export async function createCredential(assetId: string, data: {
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

// Import APIs
export async function downloadImportTemplate(
  category: string,
  mode: 'create' | 'update'
): Promise<void> {
  const response = await api.get(`/assets/import/template/${category}`, {
    params: { mode },
    responseType: 'blob'
  })

  // Create blob and trigger download
  const blob = new Blob([response.data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', mode === 'create' ? '主机创建模板.xlsx' : '主机更新模板.xlsx')
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

export interface ImportResult {
  total_rows: number
  success_count: number
  failed_count: number
  errors: Array<{ row?: number; errors?: string[]; error?: string; name?: string; id?: number }>
}

export async function importAssets(
  category: string,
  mode: 'create' | 'update',
  file: File
): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post(`/assets/import/${category}`, formData, {
    params: { mode },
    headers: { 'Content-Type': 'multipart/form-data' }
  })

  return response.data.data
}

// Export APIs
export async function exportAssets(params: {
  format: 'excel' | 'csv'
  scope: 'all' | 'selected' | 'filtered'
  category?: string
  organization_id?: number
  search?: string
  ids?: string  // Comma-separated IDs for selected scope
}): Promise<void> {
  const response = await api.get('/assets/export', {
    params,
    responseType: 'blob'
  })

  // Create blob and trigger download
  const blob = new Blob([response.data], {
    type: params.format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  // Get filename from Content-Disposition header or generate default
  const contentDisposition = response.headers['content-disposition']
  let filename = `asset_export.${params.format === 'csv' ? 'csv' : 'xlsx'}`
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?(.+?)"?$/)
    if (match) {
      try {
        filename = decodeURIComponent(match[1])
      } catch {
        // Fallback to default if decode fails
      }
    }
  }
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}