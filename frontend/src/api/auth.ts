import api from './index'
import type { LoginRequest, TokenResponse, UserSimple, ApiResponse, MFARequiredData, MFASetupQRData, MustChangePasswordData } from '@/types'

export async function login(data: LoginRequest): Promise<TokenResponse | MFARequiredData | MustChangePasswordData> {
  const response = await api.post<ApiResponse<TokenResponse | MFARequiredData | MustChangePasswordData>>('/auth/login', data)
  return response.data.data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

export async function heartbeat(): Promise<void> {
  await api.post('/auth/heartbeat')
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

export async function loginMFAVerify(userId: number, code: string, setup = false): Promise<TokenResponse> {
  const response = await api.post<ApiResponse<TokenResponse>>('/auth/mfa/login-verify', {
    user_id: userId,
    code,
    setup,
  })
  return response.data.data
}

export async function getMFASetupQR(userId: number): Promise<MFASetupQRData> {
  const response = await api.post<ApiResponse<MFASetupQRData>>(`/auth/mfa/setup-qr?user_id=${userId}`)
  return response.data.data
}

export async function resetUserMFA(userId: number): Promise<void> {
  await api.post(`/auth/mfa/reset?user_id=${userId}`)
}

export async function disableUserMFA(userId: number): Promise<void> {
  await api.post(`/auth/mfa/disable?user_id=${userId}`)
}

export async function forceChangePassword(data: {
  user_id: number
  new_password: string
  confirm_password: string
}): Promise<TokenResponse> {
  const response = await api.post<ApiResponse<TokenResponse>>('/auth/force-change-password', data)
  return response.data.data
}