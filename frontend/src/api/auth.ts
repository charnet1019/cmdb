import api from './index'
import type { LoginRequest, TokenResponse, User, ApiResponse } from '@/types'

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const response = await api.post<ApiResponse<TokenResponse>>('/auth/login', data)
  return response.data.data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

export async function getCurrentUser(): Promise<User> {
  const response = await api.get<ApiResponse<User>>('/auth/me')
  return response.data.data
}

export async function changePassword(data: {
  old_password: string
  new_password: string
  confirm_password: string
}): Promise<void> {
  await api.post('/auth/change-password', data)
}