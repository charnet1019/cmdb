import { api } from './index'

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