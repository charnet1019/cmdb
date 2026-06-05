import { computed, watch, shallowReactive, ref, type Ref, unref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { AssetCategory } from '@/types'
import { getColumnConfig, saveColumnConfig, COLUMN_SCHEMA_VERSION } from '@/api/preferences'

export interface ColumnDefinition {
  key: string
  label: string
  fixed?: boolean
  defaultVisible?: boolean
}

const categoryColumnDefs: Record<AssetCategory | 'all', ColumnDefinition[]> = {
  all: [
    { key: 'id', label: 'ID', defaultVisible: false },
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'category', label: '资产类型', defaultVisible: false },
    { key: 'platform', label: '平台/厂商', defaultVisible: true },
    { key: 'model', label: '型号', defaultVisible: false },
    { key: 'serial_number', label: '序列号', defaultVisible: false },
    { key: 'cpu', label: 'CPU', defaultVisible: false },
    { key: 'memory', label: '内存', defaultVisible: false },
    { key: 'system_disk', label: '系统盘', defaultVisible: false },
    { key: 'data_disk', label: '数据盘', defaultVisible: false },
    { key: 'oob', label: 'OOB', defaultVisible: false },
    { key: 'oob_credentials', label: 'OOB用户名密码', defaultVisible: false },
    { key: 'applicant', label: '申请人', defaultVisible: false },
    { key: 'owner', label: '负责人', defaultVisible: false },
    { key: 'runs_on', label: '运行于', defaultVisible: false },
    { key: 'storage_locations', label: '存储位置', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: true },
    { key: 'status', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: true },
    { key: 'creator', label: '创建者', defaultVisible: false },
    { key: 'created_at', label: '创建时间', defaultVisible: false },
    { key: 'updated_at', label: '更新时间', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  host: [
    { key: 'id', label: 'ID', defaultVisible: false },
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'platform', label: '平台', defaultVisible: true },
    { key: 'model', label: '型号', defaultVisible: false },
    { key: 'serial_number', label: '序列号', defaultVisible: false },
    { key: 'cpu', label: 'CPU', defaultVisible: false },
    { key: 'memory', label: '内存', defaultVisible: false },
    { key: 'system_disk', label: '系统盘', defaultVisible: false },
    { key: 'data_disk', label: '数据盘', defaultVisible: false },
    { key: 'oob', label: 'OOB', defaultVisible: false },
    { key: 'oob_credentials', label: 'OOB用户名密码', defaultVisible: false },
    { key: 'applicant', label: '申请人', defaultVisible: false },
    { key: 'owner', label: '负责人', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: true },
    { key: 'status', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: true },
    { key: 'creator', label: '创建者', defaultVisible: false },
    { key: 'created_at', label: '创建时间', defaultVisible: false },
    { key: 'updated_at', label: '更新时间', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  network: [
    { key: 'id', label: 'ID', defaultVisible: false },
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'device_type', label: '设备类型', defaultVisible: false },
    { key: 'platform', label: '厂商/型号', defaultVisible: true },
    { key: 'serial_number', label: '序列号', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: true },
    { key: 'status', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'owner', label: '负责人', defaultVisible: false },
    { key: 'notes', label: '描述', defaultVisible: true },
    { key: 'creator', label: '创建者', defaultVisible: false },
    { key: 'created_at', label: '创建时间', defaultVisible: false },
    { key: 'updated_at', label: '更新时间', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  database: [
    { key: 'id', label: 'ID', defaultVisible: false },
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'platform', label: '平台', defaultVisible: true },
    { key: 'db_type', label: '数据库类型', defaultVisible: false },
    { key: 'version', label: '版本', defaultVisible: false },
    { key: 'namespace', label: '命名空间', defaultVisible: false },
    { key: 'applicant', label: '申请人', defaultVisible: false },
    { key: 'owner', label: '负责人', defaultVisible: false },
    { key: 'runs_on', label: '运行于', defaultVisible: false },
    { key: 'storage_locations', label: '存储位置', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: true },
    { key: 'status', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: true },
    { key: 'creator', label: '创建者', defaultVisible: false },
    { key: 'created_at', label: '创建时间', defaultVisible: false },
    { key: 'updated_at', label: '更新时间', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  cloud: [
    { key: 'id', label: 'ID', defaultVisible: false },
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'platform', label: '平台', defaultVisible: true },
    { key: 'organization', label: '节点', defaultVisible: true },
    { key: 'status', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'owner', label: '负责人', defaultVisible: false },
    { key: 'notes', label: '描述', defaultVisible: true },
    { key: 'creator', label: '创建者', defaultVisible: false },
    { key: 'created_at', label: '创建时间', defaultVisible: false },
    { key: 'updated_at', label: '更新时间', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  web: [
    { key: 'id', label: 'ID', defaultVisible: false },
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'platform', label: '平台', defaultVisible: true },
    { key: 'applicant', label: '申请人', defaultVisible: false },
    { key: 'owner', label: '负责人', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: true },
    { key: 'status', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: true },
    { key: 'creator', label: '创建者', defaultVisible: false },
    { key: 'created_at', label: '创建时间', defaultVisible: false },
    { key: 'updated_at', label: '更新时间', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  gpt: [
    { key: 'id', label: 'ID', defaultVisible: false },
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'platform', label: '平台', defaultVisible: true },
    { key: 'owner', label: '负责人', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: true },
    { key: 'status', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: true },
    { key: 'creator', label: '创建者', defaultVisible: false },
    { key: 'created_at', label: '创建时间', defaultVisible: false },
    { key: 'updated_at', label: '更新时间', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ]
}

const STORAGE_KEY_PREFIX = 'cmdb_columns_'
const STORAGE_ORDER_KEY_PREFIX = 'cmdb_columns_order_'
const DEBOUNCE_DELAY = 5000

function getStorageKey(prefix: string, userId: number | undefined, category: string): string {
  return userId ? `${prefix}${userId}_${category}` : `${prefix}${category}`
}

export function useColumnConfig(category: Ref<AssetCategory | 'all'> | AssetCategory | 'all') {
  const getCategoryValue = () => unref(category)
  const authStore = useAuthStore()
  const userId = computed(() => authStore.user?.id)

  const allColumns = computed(() => {
    const cat = getCategoryValue()
    return categoryColumnDefs[cat] || categoryColumnDefs.all
  })

  const visibleColumnKeys = shallowReactive<Record<string, boolean>>({})
  const columnConfigVersion = ref(0)
  const columnOrder = ref<string[]>([])

  // Debounce timer for backend sync
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let initialLoadDone = false

  function getSavedConfigKey(): string {
    return getStorageKey(STORAGE_KEY_PREFIX, userId.value, getCategoryValue())
  }

  function getOrderKey(): string {
    return getStorageKey(STORAGE_ORDER_KEY_PREFIX, userId.value, getCategoryValue())
  }

  function loadSavedConfig(): Record<string, boolean> {
    const saved = localStorage.getItem(getSavedConfigKey())
    if (saved) {
      try { return JSON.parse(saved) } catch { return {} }
    }
    return {}
  }

  function loadSavedOrder(): string[] {
    const saved = localStorage.getItem(getOrderKey())
    if (saved) { try { return JSON.parse(saved) } catch { return [] } }
    return []
  }

  function initVisibleColumns() {
    const saved = loadSavedConfig()
    for (const key of Object.keys(visibleColumnKeys)) {
      delete visibleColumnKeys[key]
    }
    for (const col of allColumns.value) {
      if (col.fixed) {
        visibleColumnKeys[col.key] = true
      } else if (saved[col.key] !== undefined) {
        visibleColumnKeys[col.key] = saved[col.key]
      } else {
        visibleColumnKeys[col.key] = col.defaultVisible || false
      }
    }
  }

  function initColumnOrder() {
    const nonFixed = allColumns.value.filter(c => !c.fixed).map(c => c.key)
    const saved = loadSavedOrder()
    const valid = saved.filter(k => nonFixed.includes(k))
    const missing = nonFixed.filter(k => !valid.includes(k))
    columnOrder.value = [...valid, ...missing]
  }

  function saveConfig() {
    const config: Record<string, boolean> = {}
    for (const col of allColumns.value) {
      if (!col.fixed) config[col.key] = visibleColumnKeys[col.key] || false
    }
    localStorage.setItem(getSavedConfigKey(), JSON.stringify(config))
  }

  function saveOrder() {
    localStorage.setItem(getOrderKey(), JSON.stringify(columnOrder.value))
  }

  // Debounced sync to backend
  function syncToBackend() {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(async () => {
      try {
        const cat = getCategoryValue()
        await saveColumnConfig(cat, {
          column_visibility: buildVisibilityConfig(),
          column_order: [...columnOrder.value],
          version: COLUMN_SCHEMA_VERSION,
        })
      } catch {
        // Silently fail — localStorage is the source of truth
      }
    }, DEBOUNCE_DELAY)
  }

  function buildVisibilityConfig(): Record<string, boolean> {
    const config: Record<string, boolean> = {}
    for (const col of allColumns.value) {
      if (!col.fixed) config[col.key] = visibleColumnKeys[col.key] || false
    }
    return config
  }

  // Apply backend config (takes precedence over localStorage, but only if version matches)
  function applyBackendConfig(config: Awaited<ReturnType<typeof getColumnConfig>>) {
    // If backend version doesn't match current schema, discard backend config
    if (config.version !== undefined && config.version !== COLUMN_SCHEMA_VERSION) {
      return
    }
    if (config.column_visibility) {
      for (const [key, visible] of Object.entries(config.column_visibility)) {
        const col = allColumns.value.find(c => c.key === key)
        if (col && !col.fixed) {
          visibleColumnKeys[key] = visible as boolean
        }
      }
    }
    if (config.column_order) {
      const nonFixed = allColumns.value.filter(c => !c.fixed).map(c => c.key)
      const valid = config.column_order.filter(k => nonFixed.includes(k))
      const missing = nonFixed.filter(k => !valid.includes(k))
      columnOrder.value = [...valid, ...missing]
      saveOrder()
    }
    columnConfigVersion.value++
    // Update localStorage to match backend
    saveConfig()
    saveOrder()
  }

  // Load from backend asynchronously
  async function loadFromBackend() {
    try {
      const cat = getCategoryValue()
      const config = await getColumnConfig(cat)
      if (config.column_visibility || config.column_order) {
        applyBackendConfig(config)
        // If version mismatch, clear stale cache and re-init with new defaults
        if (config.version !== undefined && config.version !== COLUMN_SCHEMA_VERSION) {
          localStorage.removeItem(getSavedConfigKey())
          localStorage.removeItem(getOrderKey())
          initVisibleColumns()
          initColumnOrder()
          syncToBackend()
        }
      }
    } catch {
      // Backend config not available — use localStorage
    }
  }

  function reorderColumn(fromKey: string, toKey: string) {
    if (fromKey === toKey) return
    const arr = [...columnOrder.value]
    const fromIdx = arr.indexOf(fromKey)
    const toIdx = arr.indexOf(toKey)
    if (fromIdx === -1 || toIdx === -1) return
    arr.splice(fromIdx, 1)
    arr.splice(toIdx, 0, fromKey)
    columnOrder.value = arr
    saveOrder()
    syncToBackend()
  }

  function toggleColumn(key: string) {
    const col = allColumns.value.find(c => c.key === key)
    if (col?.fixed) return
    visibleColumnKeys[key] = !visibleColumnKeys[key]
    columnConfigVersion.value++
    saveConfig()
    syncToBackend()
  }

  async function resetColumns() {
    for (const key of Object.keys(visibleColumnKeys)) {
      delete visibleColumnKeys[key]
    }
    for (const col of allColumns.value) {
      visibleColumnKeys[col.key] = col.fixed || col.defaultVisible || false
    }
    columnConfigVersion.value++
    localStorage.removeItem(getSavedConfigKey())
    localStorage.removeItem(getOrderKey())
    initColumnOrder()
    // Clear backend config
    try {
      await saveColumnConfig(getCategoryValue(), {
        column_visibility: {},
        column_order: [],
        version: COLUMN_SCHEMA_VERSION,
      })
    } catch {
      // Ignore
    }
  }

  // Sync current category to backend immediately when switching (only if version matches)
  async function syncCurrentToBackend() {
    try {
      const cat = getCategoryValue()
      const backend = await getColumnConfig(cat)
      // Only sync if backend version matches — if not, let loadFromBackend handle the upgrade
      if (backend.version !== undefined && backend.version !== COLUMN_SCHEMA_VERSION) {
        return
      }
      await saveColumnConfig(cat, {
        column_visibility: buildVisibilityConfig(),
        column_order: [...columnOrder.value],
        version: COLUMN_SCHEMA_VERSION,
      })
    } catch {
      // Ignore
    }
  }

  watch(() => unref(category), async () => {
    if (!initialLoadDone) {
      initialLoadDone = true
    } else {
      // Sync previous category before switching
      await syncCurrentToBackend()
    }
    initVisibleColumns()
    initColumnOrder()
    // Load backend config for new category
    loadFromBackend()
  }, { immediate: true })

  // Cleanup debounce timer on unmount
  watch(
    () => columnConfigVersion.value,
    () => {
      // Triggered when visibility changes — handled by toggleColumn directly
    },
    { flush: 'pre' }
  )

  return {
    allColumns,
    visibleColumnKeys,
    columnConfigVersion,
    columnOrder,
    toggleColumn,
    resetColumns,
    reorderColumn,
    syncToBackend,
  }
}
