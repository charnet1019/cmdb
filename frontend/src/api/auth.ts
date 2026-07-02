import api from './index'
import type { LoginRequest, TokenResponse, UserSimple, ApiResponse } from '@/types'

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const response = await api.post<ApiResponse<TokenResponse>>('/auth/login', data)
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