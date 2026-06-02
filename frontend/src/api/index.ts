import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import type { ApiResponse } from '@/types'

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors
api.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      // Notify auth store to clear its token ref (prevents stale token in router guard)
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