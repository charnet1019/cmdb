import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import type { ApiResponse } from '@/types'

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    'X-CMDB-Client': 'web',
  },
})

// Response interceptor - handle errors
api.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    return response
  },
  (error) => {
    const detail = error.response?.data?.detail
    const shouldClearAuth = error.response?.status === 401
      || (error.response?.status === 403 && detail === '用户已被禁用')

    if (shouldClearAuth) {
      // Don't redirect if already on login page — MFA verification errors
      // also return 401 and we want to stay on the MFA input form.
      if (window.location.pathname === '/login') {
        return Promise.reject(error)
      }
      window.dispatchEvent(new CustomEvent('auth:token-cleared'))
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Helper function to get paginated data
async function getPaginated<T>(
  url: string,
  params: Record<string, any> = {}
): Promise<{ items: T[]; total: number; page: number; limit: number; pages: number }> {
  const response = await api.get(url, { params })
  // API returns: { code: 0, message: "success", data: [...], meta: {...} }
  const data = (response.data.data as T[]) || []
  const meta = response.data.meta || { total: 0, page: 1, limit: 20, pages: 0 }
  return {
    items: data,
    total: meta.total,
    page: meta.page,
    limit: meta.limit,
    pages: meta.pages
  }
}

export { api, getPaginated }
export default api