import { computed, watch, shallowReactive, ref, type Ref, unref } from 'vue'
import type { AssetCategory } from '@/types'

export interface ColumnDefinition {
  key: string
  label: string
  fixed?: boolean
  defaultVisible?: boolean
}

const categoryColumnDefs: Record<AssetCategory | 'all', ColumnDefinition[]> = {
  all: [
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'category', label: '资产类型', defaultVisible: true },
    { key: 'platform', label: '平台/厂商', defaultVisible: true },
    { key: 'model', label: '型号', defaultVisible: false },
    { key: 'serial_number', label: '序列号', defaultVisible: false },
    { key: 'cpu', label: 'CPU', defaultVisible: false },
    { key: 'memory', label: '内存', defaultVisible: false },
    { key: 'system_disk', label: '系统盘', defaultVisible: false },
    { key: 'data_disk', label: '数据盘', defaultVisible: false },
    { key: 'applicant', label: '申请人', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: false },
    { key: 'is_active', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  host: [
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
    { key: 'applicant', label: '申请人', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: false },
    { key: 'is_active', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  network: [
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'device_type', label: '设备类型', defaultVisible: true },
    { key: 'platform', label: '厂商/型号', defaultVisible: true },
    { key: 'serial_number', label: '序列号', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: false },
    { key: 'is_active', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  database: [
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'platform', label: '平台', defaultVisible: true },
    { key: 'db_type', label: '数据库类型', defaultVisible: true },
    { key: 'version', label: '版本', defaultVisible: false },
    { key: 'namespace', label: '命名空间', defaultVisible: false },
    { key: 'applicant', label: '申请人', defaultVisible: false },
    { key: 'organization', label: '节点', defaultVisible: false },
    { key: 'is_active', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  cloud: [
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'platform', label: '平台', defaultVisible: true },
    { key: 'organization', label: '节点', defaultVisible: false },
    { key: 'is_active', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  web: [
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'platform', label: '平台', defaultVisible: true },
    { key: 'organization', label: '节点', defaultVisible: false },
    { key: 'is_active', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ],
  gpt: [
    { key: 'name', label: '名称', fixed: true, defaultVisible: true },
    { key: 'address', label: '地址', fixed: true, defaultVisible: true },
    { key: 'asset_code', label: '资产编号', defaultVisible: false },
    { key: 'platform', label: '平台', defaultVisible: true },
    { key: 'organization', label: '节点', defaultVisible: false },
    { key: 'is_active', label: '状态', defaultVisible: true },
    { key: 'credentials', label: '用户名密码', defaultVisible: true },
    { key: 'notes', label: '描述', defaultVisible: false },
    { key: 'actions', label: '操作', fixed: true, defaultVisible: true }
  ]
}

const STORAGE_KEY_PREFIX = 'cmdb_columns_'

export function useColumnConfig(category: Ref<AssetCategory | 'all'> | AssetCategory | 'all') {
  const getCategoryValue = () => unref(category)

  const allColumns = computed(() => {
    const cat = getCategoryValue()
    return categoryColumnDefs[cat] || categoryColumnDefs.all
  })

  function loadSavedConfig(): Record<string, boolean> {
    const cat = getCategoryValue()
    const saved = localStorage.getItem(STORAGE_KEY_PREFIX + cat)
    if (saved) {
      try { return JSON.parse(saved) } catch { return {} }
    }
    return {}
  }

  const visibleColumnKeys = shallowReactive<Record<string, boolean>>({})
  const columnConfigVersion = ref(0)

  function initVisibleColumns() {
    const saved = loadSavedConfig()
    // 清除旧属性
    for (const key of Object.keys(visibleColumnKeys)) {
      delete visibleColumnKeys[key]
    }
    // 设置新属性
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

  function toggleColumn(key: string) {
    const col = allColumns.value.find(c => c.key === key)
    if (col?.fixed) return
    visibleColumnKeys[key] = !visibleColumnKeys[key]
    columnConfigVersion.value++
    saveConfig()
  }

  function saveConfig() {
    const config: Record<string, boolean> = {}
    for (const col of allColumns.value) {
      if (!col.fixed) config[col.key] = visibleColumnKeys[col.key] || false
    }
    localStorage.setItem(STORAGE_KEY_PREFIX + getCategoryValue(), JSON.stringify(config))
  }

  function resetColumns() {
    for (const key of Object.keys(visibleColumnKeys)) {
      delete visibleColumnKeys[key]
    }
    for (const col of allColumns.value) {
      visibleColumnKeys[col.key] = col.fixed || col.defaultVisible || false
    }
    columnConfigVersion.value++
    localStorage.removeItem(STORAGE_KEY_PREFIX + getCategoryValue())
  }

  watch(() => unref(category), () => {
    initVisibleColumns()
  }, { immediate: true })

  return {
    allColumns,
    visibleColumnKeys,
    columnConfigVersion,
    toggleColumn,
    resetColumns
  }
}
