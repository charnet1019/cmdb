/**
 * Assets data management composable
 * Handles fetching, creating, updating, deleting assets
 */
import { ref, computed } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  getAssets,
  deleteAsset,
  getAssetStats,
  bulkUpdateAssets,
  bulkDeleteAssets
} from '@/api/assets'
import type { Asset, AssetCategory } from '@/types'

// Extended asset type with runtime properties for UI state
export interface AssetWithUI extends Asset {
  expandedNotes?: boolean
  selected?: boolean
  creator_name?: string
}

// Asset statistics
export interface AssetStats {
  total: number
  by_category: Record<string, number>
  by_platform: Record<string, number>
  by_device_type: Record<string, number>
}

export function useAssets() {
  // Data
  const assets = ref<AssetWithUI[]>([])
  const loading = ref(false)
  const total = ref(0)
  const page = ref(1)
  const limit = ref(20)

  // Asset statistics
  const assetStats = ref<AssetStats>({
    total: 0,
    by_category: {},
    by_platform: {},
    by_device_type: {}
  })

  // Bulk selection
  const allSelected = ref(false)

  // Selected counts
  const selectedCount = computed(() => assets.value.filter(asset => asset.selected).length)
  const selectedIds = computed(() => assets.value.filter(asset => asset.selected).map(asset => String(asset.id)))

  // Fetch assets
  async function fetchAssets(params: {
    category?: AssetCategory | 'all'
    search?: string
    organizationId?: number | null
    status?: string
  }) {
    loading.value = true
    try {
      const result = await getAssets({
        page: page.value,
        limit: limit.value,
        category: params.category !== 'all' ? params.category : undefined,
        search: params.search || undefined,
        organization_id: params.organizationId || undefined,
        status: params.status || undefined
      })
      assets.value = (result.items || []).map(asset => ({
        ...asset,
        expandedNotes: false,
        selected: false
      }))
      total.value = result.total || 0
    } catch (error) {
      message.error('获取资产列表失败')
      assets.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  // Fetch asset statistics
  async function fetchAssetStats() {
    try {
      assetStats.value = await getAssetStats()
    } catch (error) {
      console.error('Failed to fetch asset stats')
    }
  }

  // Handle page change
  function handlePageChange(newPage: number, fetchFn: () => void) {
    page.value = newPage
    fetchFn()
  }

  // Selection functions
  function selectAllChanged(event: Event) {
    const target = event.target as HTMLInputElement
    const checked = target.checked
    allSelected.value = checked
    assets.value.forEach(asset => {
      asset.selected = checked
    })
  }

  function selectionChanged() {
    allSelected.value = assets.value.every(asset => asset.selected)
  }

  function getSelectedAssetIds(): string[] {
    return assets.value.filter(asset => asset.selected).map(asset => asset.id)
  }

  // Delete single asset
  async function handleDelete(asset: Asset, fetchFn: () => void, onDeleted?: () => void) {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除资产 "${asset.name}" 吗？删除后无法恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      async onOk() {
        try {
          await deleteAsset(asset.id)
          message.success('资产已删除')
          fetchFn()
          fetchAssetStats()
          onDeleted?.()
        } catch (error) {
          message.error('删除失败')
        }
      }
    })
  }

  async function bulkDelete(fetchFn: () => void, onDeleted?: () => void) {
    const ids = getSelectedAssetIds()
    if (ids.length === 0) {
      message.warning('请先选择要删除的资产')
      return
    }

    Modal.confirm({
      title: '确认删除',
      content: `确定要删除选中的 ${ids.length} 个资产吗？删除后无法恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      async onOk() {
        try {
          await bulkDeleteAssets(ids)
          message.success(`已删除 ${ids.length} 个资产`)
          allSelected.value = false
          fetchFn()
          fetchAssetStats()
          onDeleted?.()
        } catch (error: any) {
          message.error(error.response?.data?.detail || '批量删除失败')
        }
      }
    })
  }

  async function bulkUpdateStatus(statusValue: string, fetchFn: () => void) {
    const ids = getSelectedAssetIds()
    if (ids.length === 0) {
      message.warning('请先选择要修改的资产')
      return
    }

    const statusLabels: Record<string, string> = {
      'inventory': '库存',
      'deploying': '部署中',
      'running': '运行中',
      'maintenance': '维护中',
      'deactivated': '停用',
      'pending_scrap': '待报废',
      'scrapped': '已报废',
      'returned': '已退还'
    }

    Modal.confirm({
      title: '确认修改状态',
      content: `确定要将选中的 ${ids.length} 个资产的状态修改为「${statusLabels[statusValue] || statusValue}」吗？`,
      okText: '确定',
      cancelText: '取消',
      centered: true,
      async onOk() {
        try {
          await bulkUpdateAssets(ids, { status: statusValue })
          message.success(`已更新 ${ids.length} 个资产的状态`)
          fetchFn()
          fetchAssetStats()
        } catch (error: any) {
          message.error(error.response?.data?.detail || '批量修改状态失败')
        }
      }
    })
  }

  return {
    // State
    assets,
    loading,
    total,
    page,
    limit,
    assetStats,
    allSelected,
    selectedCount,
    selectedIds,

    // Actions
    fetchAssets,
    fetchAssetStats,
    handlePageChange,
    selectAllChanged,
    selectionChanged,
    bulkDelete,
    bulkUpdateStatus,
    handleDelete
  }
}