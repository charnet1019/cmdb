import api from './index'
import type { LoginRequest, TokenResponse, UserSimple, ApiResponse, MFARequiredData, MFASetupQRData, MustChangePasswordData } from '@/types'

export async function login(data: LoginRequest): Promise<TokenResponse | MFARequiredData | MustChangePasswordData> {
  const response = await api.post<ApiResponse<TokenResponse | MFARequiredData | MustChangePasswordData>>('/auth/login', data, { timeout: 10000 })
  return response.data.data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

export async function heartbeat(userActive = false): Promise<{ expires_at?: string | null }> {
  const response = await api.post<ApiResponse<{ expires_at?: string | null }>>(
    '/auth/heartbeat',
    null,
    { headers: { 'X-CMDB-User-Active': userActive ? '1' : '0' } }
  )
  return response.data.data || {}
}

export async function getCurrentUser(): Promise<UserSimple> {
  const response = await api.get<ApiResponse<UserSimple>>('/auth/me')
  return response.data.data
}

export async function changePassword(data: {
  old_password: string
  new_password: string
  confirm_password: string
}): Promise<void> {
  await api.post('/auth/change-password', data)
}

export async function uploadAvatar(file: File): Promise<{ avatar_url: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<ApiResponse<{ avatar_url: string }>>('/auth/avatar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data.data
}

export async function deleteAvatar(): Promise<void> {
  await api.delete('/auth/avatar')
}

export async function loginMFAVerify(challengeToken: string, code: string, setup = false): Promise<TokenResponse> {
  const response = await api.post<ApiResponse<TokenResponse>>('/auth/mfa/login-verify', {
    challenge_token: challengeToken,
    code,
    setup,
  })
  return response.data.data
}

export async function getMFASetupQR(challengeToken: string): Promise<MFASetupQRData> {
  const response = await api.post<ApiResponse<MFASetupQRData>>('/auth/mfa/setup-qr', null, {
    params: { challenge_token: challengeToken },
  })
  return response.data.data
}

export async function resetUserMFA(userId: number): Promise<void> {
  await api.post(`/auth/mfa/reset?user_id=${userId}`)
}

export async function disableUserMFA(userId: number): Promise<void> {
  await api.post(`/auth/mfa/disable?user_id=${userId}`)
}

export async function forceChangePassword(data: {
  challenge_token: string
  new_password: string
  confirm_password: string
}): Promise<TokenResponse | MFARequiredData> {
  const response = await api.post<ApiResponse<TokenResponse | MFARequiredData>>('/auth/force-change-password', data)
  return response.data.data
}