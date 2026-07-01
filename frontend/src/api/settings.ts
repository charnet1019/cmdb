import { api } from './index'

// Upload image file
export async function uploadImage(file: File): Promise<{ url: string; filename: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post('/upload/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data.data
}

// Delete image file
export async function deleteImage(filename: string): Promise<void> {
  await api.delete(`/upload/image/${filename}`)
}

// Public API client (no auth token required)
const publicApi = {
  async get(path: string): Promise<any> {
    const response = await fetch(`/api/v1${path}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    return response.json()
  },
}

export interface SettingRaw {
  id: number
  key: string
  value: { value: any }
  description: string | null
  updated_at: string | null
}

export interface SettingsResponse {
  data: Record<string, any>
  raw: SettingRaw[]
}

// Get all settings
export async function getSettings(): Promise<SettingsResponse> {
  const response = await api.get('/settings')
  // API returns: { code: 0, message: "success", data: {...}, raw: [...] }
  return {
    data: response.data.data,
    raw: response.data.raw
  }
}

// Update multiple settings
export async function updateSettings(settings: Record<string, any>): Promise<{ updated: string[]; message: string }> {
  const response = await api.put('/settings', settings)
  return response.data.data
}

// Get public branding settings (no auth required)
export async function getPublicSettings(): Promise<Record<string, any>> {
  const data = await publicApi.get('/settings/public')
  return data.data
}