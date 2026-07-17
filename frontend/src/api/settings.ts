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
const PUBLIC_REQUEST_TIMEOUT_MS = 10000

const publicApi = {
  async get(path: string): Promise<any> {
    const controller = new AbortController()
    const timeoutId = window.setTimeout(() => controller.abort(), PUBLIC_REQUEST_TIMEOUT_MS)
    try {
      const response = await fetch(`/api/v1${path}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      return response.json()
    } finally {
      window.clearTimeout(timeoutId)
    }
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
export async function updateSettings(settings: Record<string, any>): Promise<{ updated: string[]; message: string; session_expires_at?: string | null }> {
  const response = await api.put('/settings', settings)
  return response.data.data
}

// Get public branding settings (no auth required)
export async function getPublicSettings(): Promise<Record<string, any>> {
  const data = await publicApi.get('/settings/public')
  return data.data
}

export interface TestEmailPayload {
  recipient: string
  smtp_host?: string
  smtp_port?: number
  smtp_encryption?: string
  smtp_username?: string
  smtp_password?: string
  smtp_from_email?: string
  smtp_from_name?: string
}

// Send a test email using the currently-edited (unsaved) or saved SMTP config
export async function sendTestEmail(payload: TestEmailPayload): Promise<{ recipient: string }> {
  const response = await api.post('/settings/email/test', payload)
  return response.data.data
}

// Decrypt and reveal the currently-saved SMTP password
export async function revealSmtpPassword(): Promise<{ password: string }> {
  const response = await api.post('/settings/smtp-password/reveal')
  return response.data.data
}