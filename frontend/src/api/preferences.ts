import { api } from './index'

export const COLUMN_SCHEMA_VERSION = 4

export interface ColumnConfig {
  column_visibility?: Record<string, boolean>
  column_order?: string[]
}

export interface ColumnConfigResponse extends ColumnConfig {
  version?: number
}

export async function getColumnConfig(category: string): Promise<ColumnConfigResponse> {
  const response = await api.get(`/preferences/columns/${category}`)
  return response.data.data
}

export async function saveColumnConfig(
  category: string,
  data: ColumnConfig & { version?: number },
): Promise<void> {
  await api.put(`/preferences/columns/${category}`, data)
}
