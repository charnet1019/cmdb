<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Dropdown, Select, Tooltip } from 'ant-design-vue'
import {
  DownOutlined,
  UpOutlined,
  RightOutlined,
  DeleteOutlined,
  CloseOutlined,
  FolderOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  CopyOutlined,
  AppstoreOutlined,
  EditOutlined,
  FolderAddOutlined,
  PlusCircleOutlined,
  SettingOutlined,
  ExportOutlined,
  ReloadOutlined,
  ImportOutlined,
  SearchOutlined
} from '@ant-design/icons-vue'
import { useAssets } from './composables/useAssets'
import { useOrganizations } from './composables/useOrganizations'
import { useCredentials } from './composables/useCredentials'
import { useTypeTree, categories, platformOptions, categoryOptions, dbTypeOptions } from './composables/useTypeTree'
import { useColumnConfig } from './composables/useColumnConfig'
import { createAsset, updateAsset, createCredential, updateCredential, getAssets, decryptOobPassword } from '@/api/assets'
import { getUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import ColumnCustomizer from './components/ColumnCustomizer.vue'
import { formatDateTime } from '@/utils/datetime'
import ImportModal from './components/ImportModal.vue'
import ExportModal from './components/ExportModal.vue'
import type { Asset, AssetCategory } from '@/types'

// Router for URL state persistence
const route = useRoute()
const router = useRouter()

// Update URL query parameters to persist state
function updateUrlState(params: { tree?: 'asset' | 'type'; org?: number | null; type?: string }) {
  const query: Record<string, string | undefined> = {}

  // Keep tree mode
  if (params.tree) {
    query.tree = params.tree
  }

  // Keep org id (asset tree node)
  if (params.org !== undefined && params.org !== null) {
    query.org = String(params.org)
  }

  // Keep type node id (type tree node)
  if (params.type !== undefined && params.type !== 'all') {
    query.type = params.type
  }

  router.replace({ query })
}

// Use composables
const {
  assets,
  loading,
  total,
  page,
  limit,
  assetStats,
  allSelected,
  selectedCount,
  selectedIds,
  fetchAssets,
  fetchAssetStats,
  handlePageChange,
  handleLimitChange,
  selectAllChanged,
  selectionChanged,
  bulkDelete,
  bulkUpdateStatus,
  handleDelete
} = useAssets()

const {
  totalAssetCount,
  isRootExpanded,
  selectedOrgId,
  expandedOrgIds,
  organizations,
  flattenedOrgs,
  allOrgsForSelect,
  showOrgContextMenu,
  orgContextMenuPosition,
  orgContextMenuTarget,
  showOrgModal,
  orgModalMode,
  orgModalLoading,
  orgForm,
  draggedOrgId,
  dragOverOrgId,
  fetchOrganizations,
  toggleOrg,
  isOrgExpanded,
  toggleRootExpansion,
  handleOrgContextMenu,
  openCreateOrgModal,
  openRenameOrgModal,
  handleOrgModalSubmit,
  handleDeleteOrg,
  handleOrgDragStart,
  handleOrgDragOver,
  handleOrgDragLeave,
  handleOrgDrop,
  handleOrgDragEnd,
  getOrgPath
} = useOrganizations()

const {
  decryptedPasswords,
  decryptedFormPasswords,
  visibleNewPasswords,
  formCredentials,
  newCredentialForm,
  credentialInputRefs,
  copyUsername,
  copyPassword,
  copyOobPassword,
  viewPassword,
  viewFormCredentialPassword,
  addCredentialToForm,
  removeCredentialFromForm,
  startFieldEdit,
  stopFieldEdit,
  isFieldEditing,
  resetFormCredentials
} = useCredentials()

// Auth for permission checks
const authStore = useAuthStore()
const hasPermission = (perm: string) => authStore.hasPermission(perm)

const {
  expandedTypeIds,
  selectedTypeNodeId,
  activeCategory,
  flattenedTypeTree,
  selectedTypeNode,
  toggleType,
  isSelectedTypeNode,
  selectType,
  getCategoryIcon
} = useTypeTree(assetStats)

// Column customization
const {
  allColumns: allColumnsConfig,
  visibleColumnKeys,
  columnConfigVersion,
  columnOrder,
  toggleColumn,
  resetColumns,
  reorderColumn
} = useColumnConfig(activeCategory)
const showColumnCustomizer = ref(false)
const showImportModal = ref(false)
const showExportModal = ref(false)

// Column drag-to-reorder
const FIXED_COLS = new Set(['checkbox', 'name', 'actions'])

const orderedColumns = computed(() => {
  const categoryKeys = new Set(allColumnsConfig.value.map((c: any) => c.key))
  const middle = columnOrder.value.filter(k => categoryKeys.has(k) && k !== 'id')
  const idCol = visibleColumnKeys['id'] ? ['id'] : []
  // address 是固定列但不在 FIXED_COLS 中，需要显式添加
  const addressCol = visibleColumnKeys['address'] && categoryKeys.has('address') ? ['address'] : []
  return ['checkbox', ...idCol, 'name', ...addressCol, ...middle, 'actions']
})

function isColVisible(key: string): boolean {
  if (FIXED_COLS.has(key)) return true
  if (!visibleColumnKeys[key]) return false
  const cat = activeCategory.value
  switch (key) {
    case 'device_type': return cat === 'network'
    case 'model': return cat === 'host' || cat === 'all'
    case 'serial_number': return cat === 'host' || cat === 'network' || cat === 'all'
    case 'cpu': case 'memory': case 'system_disk': case 'data_disk':
    case 'oob': case 'oob_credentials': return cat === 'host' || cat === 'all'
    case 'db_type': case 'version': case 'namespace': return cat === 'database' || cat === 'all'
    case 'runs_on': case 'storage_locations': return cat === 'database' || cat === 'all'
    case 'applicant': return cat === 'host' || cat === 'database' || cat === 'web' || cat === 'all'
    case 'owner': return true // 负责人所有类别都显示
    default: return true
  }
}

function thLabel(key: string): string {
  // 动态列映射：通过表头名称匹配
  const col = allColumnsConfig.value.find((c: any) => c.key === key)
  if (col) return col.label

  // 降级处理：对于 platform 字段，统一返回'平台'
  if (key === 'platform') return '平台'
  return key
}

const dragFromKey = ref('')
const dragOverKey = ref('')
function handleColDragStart(key: string, e: DragEvent) {
  dragFromKey.value = key
  e.dataTransfer?.setData('text/plain', key)
}
function handleColDragOver(key: string, e: DragEvent) {
  e.preventDefault()
  dragOverKey.value = key
}
function handleColDrop(toKey: string, e: DragEvent) {
  e.preventDefault()
  dragOverKey.value = ''
  if (dragFromKey.value) reorderColumn(dragFromKey.value, toKey)
  dragFromKey.value = ''
}
function handleColDragEnd() {
  dragFromKey.value = ''
  dragOverKey.value = ''
}

// Password popover
const passwordPopover = ref<{ credId: number; password: string; x: number; y: number } | null>(null)

async function showPasswordPopover(cred: { id: number }, event: MouseEvent) {
  if (passwordPopover.value?.credId === cred.id) {
    passwordPopover.value = null
    return
  }
  try {
    await viewPassword(cred)
    const password = decryptedPasswords.value.get(cred.id)
    if (password) {
      const rect = (event.target as HTMLElement).getBoundingClientRect()
      passwordPopover.value = { credId: cred.id, password, x: rect.left, y: rect.top }
      // viewPassword toggles — re-hide from decryptedPasswords to keep table clean
      decryptedPasswords.value.delete(cred.id)
    }
  } catch (e: any) {
    message.error(e.response?.data?.detail || '解密失败')
  }
}

function closePasswordPopover() {
  passwordPopover.value = null
}

async function showOobPasswordPopover(asset: any, event: MouseEvent) {
  if (!asset.oob_username && !asset.extra_data?.oob_username) return
  if (passwordPopover.value?.credId === -asset.id) {
    passwordPopover.value = null
    return
  }
  try {
    const data = await decryptOobPassword(asset.id)
    const rect = (event.target as HTMLElement).getBoundingClientRect()
    passwordPopover.value = { credId: -asset.id, password: data.oob_password, x: rect.left, y: rect.top }
  } catch {
    message.error('解密失败')
  }
}

// Tree view mode
const treeViewMode = ref<'asset' | 'type'>('asset')

// Search
const searchQuery = ref('')
const statusFilter = ref('')

// Modal
const showModal = ref(false)
const showPassword = ref(false)
const showOobPassword = ref(false)
const modalLoading = ref(false)
const editingAsset = ref<Asset | null>(null)
const formSelectedOrgId = ref<number | null>(null)

// Device type options for network
const localDeviceTypeOptions = ['交换机', '路由器', '防火墙', '负载均衡', '无线控制器']

// Asset status options
const statusOptions = [
  { key: 'inventory', label: '库存' },
  { key: 'deploying', label: '部署中' },
  { key: 'running', label: '运行中' },
  { key: 'maintenance', label: '维护中' },
  { key: 'deactivated', label: '停用' },
  { key: 'pending_scrap', label: '待报废' },
  { key: 'scrapped', label: '已报废' },
  { key: 'returned', label: '已退还' }
]

function getStatusLabel(value: string) {
  return statusOptions.find(s => s.key === value)?.label || value
}

function getStatusColor(value: string): string {
  const colors: Record<string, string> = {
    'inventory': 'bg-blue-100 text-blue-700',
    'deploying': 'bg-yellow-100 text-yellow-700',
    'running': 'bg-green-100 text-green-700',
    'maintenance': 'bg-orange-100 text-orange-700',
    'deactivated': 'bg-red-100 text-red-700',
    'pending_scrap': 'bg-amber-100 text-amber-700',
    'scrapped': 'bg-gray-200 text-gray-600',
    'returned': 'bg-purple-100 text-purple-700'
  }
  return colors[value] || 'bg-slate-100 text-slate-600'
}

// User list for owner selection
const userOptions = ref<Array<{ id: number; username: string; full_name: string | null }>>([])
const loadingUsers = ref(false)

// Host list for runs_on selection in database asset forms
const hostOptions = ref<Array<{ id: string; name: string; internal_address: string | null }>>([])
const hostSearchQuery = ref('')

// Filtered host options based on search input
const filteredHostOptions = computed(() => {
  const query = hostSearchQuery.value.trim().toLowerCase()
  if (!query) return hostOptions.value
  return hostOptions.value.filter(h => {
    const nameMatch = h.name.toLowerCase().includes(query)
    const address = (h.internal_address || '').toLowerCase()
    const addressMatch = address.includes(query)
    return nameMatch || addressMatch
  })
})

function onHostSearch(value: string) {
  hostSearchQuery.value = value
}

// Load users for owner dropdown
async function loadUsers() {
  if (userOptions.value.length > 0) return
  loadingUsers.value = true
  try {
    const result = await getUsers({ page: 1, limit: 100 })
    userOptions.value = (result.items || []).map(u => ({
      id: u.id,
      username: u.username,
      full_name: u.full_name
    }))
  } catch (error) {
    console.error('Failed to load users:', error)
  } finally {
    loadingUsers.value = false
  }
}

// Load hosts for runs_on dropdown in database asset forms
async function loadHostOptions() {
  if (hostOptions.value.length > 0) return
  try {
    const result = await getAssets({ category: 'host', page: 1, limit: 100 })
    hostOptions.value = (result.items || []).map(h => ({
      id: String(h.id),
      name: h.name,
      internal_address: h.internal_address
    }))
  } catch (error) {
    console.error('Failed to load hosts:', error)
  }
}

// Form
const form = ref({
  name: '',
  asset_code: '',
  category: 'host' as AssetCategory,
  internal_address: '',
  external_address: '',
  platform: '',
  status: '',
  device_type: '',
  model: '',
  serial_number: '',
  cpu: '',
  memory: '',
  system_disk: '',
  data_disk: '',
  version: '',
  namespace: '',
  db_type: activeCategory.value === 'database' ? 'MySQL' : '',
  oob: '',
  oob_username: '',
  oob_password: '',
  applicant: '',
  owner_id: null as number | null,
  notes: '',
  host_ids: [] as string[],
  storage_locations: [] as { path: string; path_type: string; description: string }[]
})

// Modal title
const modalTitle = computed(() => editingAsset.value ? '编辑资产' : '创建资产')
// Fetch data function
function fetchData() {
  const subCat = selectedTypeNode.value?.subCategory
  fetchAssets({
    category: activeCategory.value,
    search: searchQuery.value,
    organizationId: selectedOrgId.value,
    status: statusFilter.value || undefined,
    platform: subCat && activeCategory.value !== 'network' && activeCategory.value !== 'database' ? subCat : undefined,
    deviceType: subCat && activeCategory.value === 'network' ? subCat : undefined,
    dbType: subCat && activeCategory.value === 'database' ? subCat : undefined
  })
}

// Handle search
function handleSearch() {
  page.value = 1
  fetchData()
}

function onStatusFilterChange() {
  page.value = 1
  fetchData()
}

// Handle import success - refresh data
function handleImportSuccess() {
  fetchData()
  fetchAssetStats()
  fetchOrganizations()
}

// Switch tree view
function switchTreeView(mode: 'asset' | 'type') {
  treeViewMode.value = mode
  if (mode === 'asset') {
    selectedOrgId.value = null
    activeCategory.value = 'all'
    updateUrlState({ tree: 'asset', org: null })
  } else {
    selectedTypeNodeId.value = 'all'
    activeCategory.value = 'all'
    selectedOrgId.value = null
    // Ensure root is expanded when switching to type tree
    if (!expandedTypeIds.value.includes('all')) {
      expandedTypeIds.value.push('all')
    }
    updateUrlState({ tree: 'type', type: 'all' })
    // Refresh stats in case assets changed while in asset-tree mode
    fetchAssetStats()
  }
  fetchData()
}

// Change category tab
function changeCategory(category: AssetCategory | 'all') {
  activeCategory.value = category
  selectedTypeNodeId.value = category === 'all' ? 'all' : category
  // Clear org selection when switching to specific category to show all assets of that type
  selectedOrgId.value = null
  if (category === 'all') {
    treeViewMode.value = 'asset'
    updateUrlState({ tree: 'asset', org: null })
  } else {
    treeViewMode.value = 'type'
    if (!expandedTypeIds.value.includes('all')) {
      expandedTypeIds.value.push('all')
    }
    updateUrlState({ tree: 'type', type: category })
  }
  page.value = 1
  fetchData()
}

// Handle root click - select root and refresh assets
function handleRootClick() {
  selectedOrgId.value = null
  selectedTypeNodeId.value = 'all'
  activeCategory.value = 'all'
  page.value = 1
  updateUrlState({ tree: 'asset', org: null })
  fetchData()
  toggleRootExpansion()
}

// Handle org click - always select and refresh, plus toggle if has children
function handleOrgClick(org: { id: number; name: string; hasChildren: boolean }) {
  selectedOrgId.value = org.id
  activeCategory.value = 'all'
  page.value = 1
  updateUrlState({ tree: 'asset', org: org.id })
  fetchData()
  if (org.hasChildren) {
    toggleOrg(org.id)
  }
}

// Handle type selection
function handleSelectType(node: any) {
  selectType(node, (category) => {
    activeCategory.value = category
    selectedOrgId.value = null
    page.value = 1
    updateUrlState({ tree: 'type', type: selectedTypeNodeId.value })
    fetchData()
  })
}

// Open create modal
async function openCreateModal() {
  editingAsset.value = null
  const defaultCategory = activeCategory.value !== 'all' ? activeCategory.value : 'host'
  form.value = {
    name: '',
    asset_code: '',
    category: defaultCategory,
    internal_address: '',
    external_address: '',
    platform: defaultCategory === 'database' ? 'Kubernetes' : defaultCategory === 'cloud' ? 'Proxmox' : '',
    status: '',
    device_type: '',
    model: '',
    serial_number: '',
    cpu: '',
    memory: '',
    system_disk: '',
    data_disk: '',
    version: '',
    namespace: '',
    db_type: activeCategory.value === 'database' ? 'MySQL' : '',
    oob: '',
    oob_username: '',
    oob_password: '',
    applicant: '',
    owner_id: null,
    notes: '',
    host_ids: [],
    storage_locations: []
  }
  if (selectedTypeNode.value && selectedTypeNode.value.category) {
    const node = selectedTypeNode.value
    form.value.category = node.category as AssetCategory
    if (node.subCategory) {
      if (node.category === 'network') {
        form.value.device_type = node.subCategory
      } else {
        form.value.platform = node.subCategory
      }
    }
  }

  await loadUsers()
  resetFormCredentials()
  if (form.value.category === 'database') {
    await loadHostOptions()
  }
  showModal.value = true
}

// Open edit modal
async function openEditModal(asset: Asset) {
  editingAsset.value = asset
  showOobPassword.value = false
  form.value = {
    name: asset.name,
    asset_code: asset.asset_code || '',
    category: asset.category,
    internal_address: asset.internal_address || '',
    external_address: asset.external_address || '',
    platform: asset.platform || '',
    status: asset.status || '',
    device_type: asset.device_type || '',
    model: asset.model || '',
    serial_number: asset.serial_number || '',
    cpu: asset.cpu || '',
    memory: asset.memory || '',
    system_disk: asset.system_disk || '',
    data_disk: asset.data_disk || '',
    version: asset.extra_data?.version || '',
    namespace: asset.namespace || '',
    db_type: asset.db_type || '',
    oob: asset.oob_address || asset.extra_data?.oob || '',
    oob_username: asset.oob_username || asset.extra_data?.oob_username || '',
    oob_password: '', // Will be decrypted below if exists
    applicant: asset.applicant || '',
    owner_id: asset.owner_id || null,
    notes: asset.notes || '',
    host_ids: (asset.runs_on_hosts || []).map(h => h.id),
    storage_locations: (asset.storage_locations || []).map(sl => ({
      path: sl.path,
      path_type: sl.path_type,
      description: sl.description || ''
    }))
  }
  formSelectedOrgId.value = asset.organization_id || null
  formCredentials.value = (asset.credentials || []).map(c => ({
    id: c.id,
    username: c.username,
    password: ''
  }))
  // Decrypt OOB password for host assets when editing
  if (asset.category === 'host' && (asset.oob_username || asset.oob_address)) {
    try {
      const data = await decryptOobPassword(asset.id)
      if (data.oob_password) {
        form.value.oob_password = data.oob_password
      }
    } catch {
      // Ignore — password field will remain empty
    }
  }
  await loadUsers()
  if (asset.category === 'database') {
    await loadHostOptions()
  }
  showModal.value = true
}

// Submit form
async function handleSubmit() {
  if (!form.value.name) {
    message.error('请输入资产名称')
    return
  }

  modalLoading.value = true
  try {
    // Prepare extra_data for database assets only (host OOB fields now use independent columns)
    let extraData: Record<string, any> | undefined
    if (form.value.category === 'database') {
      const extraFields: Record<string, any> = {}
      if (form.value.version) extraFields.version = form.value.version
      extraData = Object.keys(extraFields).length > 0 ? extraFields : undefined
    }

    const data: Record<string, any> = {
      name: form.value.name,
      // Only include asset_code if form has a value (empty string is valid to clear it)
      ...(form.value.asset_code !== '' && { asset_code: form.value.asset_code }),
      category: form.value.category,
      internal_address: form.value.internal_address || undefined,
      external_address: form.value.external_address || undefined,
      platform: form.value.platform || undefined,
      status: form.value.status || undefined,
      device_type: form.value.device_type || undefined,
      model: form.value.model || undefined,
      serial_number: form.value.serial_number || undefined,
      cpu: form.value.cpu || undefined,
      memory: form.value.memory || undefined,
      system_disk: form.value.system_disk || undefined,
      data_disk: form.value.data_disk || undefined,
      // Independent fields for database assets
      db_type: form.value.db_type || undefined,
      applicant: form.value.applicant || undefined,
      namespace: form.value.namespace || undefined,
      owner_id: form.value.owner_id || undefined,
      // Independent OOB fields for host assets
      ...(form.value.category === 'host' && {
        oob_address: form.value.oob || undefined,
        oob_username: form.value.oob_username || undefined,
        oob_password: form.value.oob_password || undefined
      }),
      extra_data: extraData,
      notes: form.value.notes || undefined,
      organization_id: formSelectedOrgId.value || undefined,
      ...(form.value.category === 'database' && {
        host_ids: form.value.host_ids.length > 0 ? form.value.host_ids : undefined,
        storage_locations: form.value.storage_locations.length > 0 ? form.value.storage_locations : undefined
      })
    }

    if (editingAsset.value) {
      await updateAsset(editingAsset.value.id, data)
      // Handle credentials: create new ones and update existing ones
      for (const cred of formCredentials.value) {
        if (cred.username) {
          if (cred.id && cred.password) {
            await updateCredential(cred.id, {
              username: cred.username,
              password: cred.password
            })
          } else if (!cred.id && cred.password) {
            await createCredential(editingAsset.value.id, {
              username: cred.username,
              password: cred.password,
              credential_type: 'password'
            })
          }
        }
      }
      message.success('资产更新成功')
    } else {
      const newAsset = await createAsset(data)
      // Create all credentials that have both username and password
      for (const cred of formCredentials.value) {
        if (cred.username && cred.password && newAsset.id) {
          await createCredential(newAsset.id, {
            username: cred.username,
            password: cred.password,
            credential_type: 'password'
          })
        }
      }
      message.success('资产创建成功')
    }

    showModal.value = false
    page.value = 1
    fetchData()
    fetchAssetStats()
    fetchOrganizations()
  } catch (error: any) {
    message.error(error.response?.data?.detail || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

onMounted(async () => {
  // Restore state from URL query parameters
  const urlTree = route.query.tree as 'asset' | 'type' | undefined
  const urlOrg = route.query.org ? Number(route.query.org) : null
  const urlType = route.query.type as string | undefined

  // Helper function to expand parent chain for an org node
  function expandParentChain(orgId: number, orgs: any[], parentPath: number[] = []) {
    for (const org of orgs) {
      if (org.id === orgId) {
        // Expand all ancestors
        for (const ancestorId of parentPath) {
          expandedOrgIds.value.add(ancestorId)
        }
        return true
      }
      if (org.children && org.children.length > 0) {
        if (expandParentChain(orgId, org.children, [...parentPath, org.id])) {
          return true
        }
      }
    }
    return false
  }

  // First load organizations to get tree data
  await fetchOrganizations()

  if (urlTree === 'asset' && urlOrg !== null) {
    // Asset tree mode with specific org node
    treeViewMode.value = 'asset'
    selectedOrgId.value = urlOrg
    activeCategory.value = 'all'
    isRootExpanded.value = true
    // Expand parent chain to show selected node
    expandParentChain(urlOrg, organizations.value)
  } else if (urlTree === 'type' && urlType) {
    // Type tree mode with specific type node
    treeViewMode.value = 'type'
    selectedTypeNodeId.value = urlType
    // Ensure root is expanded so type tree is visible
    if (!expandedTypeIds.value.includes('all')) {
      expandedTypeIds.value.push('all')
    }
    // Determine category from type node
    if (urlType.includes('-')) {
      // Sub-category like 'network-交换机'
      activeCategory.value = urlType.split('-')[0] as AssetCategory
    } else if (urlType !== 'all') {
      // Main category like 'host'
      activeCategory.value = urlType as AssetCategory
    } else {
      activeCategory.value = 'all'
    }
  } else if (urlOrg !== null) {
    // Legacy: org parameter without tree mode
    treeViewMode.value = 'asset'
    selectedOrgId.value = urlOrg
    activeCategory.value = 'all'
    isRootExpanded.value = true
    // Expand parent chain to show selected node
    expandParentChain(urlOrg, organizations.value)
  } else {
    // Default state
    treeViewMode.value = 'asset'
    selectedOrgId.value = null
    activeCategory.value = 'all'
  }

  fetchData()
  fetchAssetStats()
})
</script>

<template>
  <div class="space-y-[1px]" @click="closePasswordPopover">
    <!-- Password popover -->
    <Teleport to="body">
      <div
        v-if="passwordPopover"
        class="fixed z-[100] bg-slate-900 text-white text-xs font-mono px-3 py-2 rounded-lg shadow-lg pointer-events-none"
        :style="{ left: passwordPopover.x + 'px', top: (passwordPopover.y - 40) + 'px' }"
      >{{ passwordPopover.password }}</div>
    </Teleport>
    <!-- Category Tabs -->
    <div class="bg-white rounded-xl shadow-sm overflow-x-auto">
      <div class="flex border-b border-slate-100">
        <button
          v-for="cat in categories"
          :key="cat.key"
          @click="changeCategory(cat.key as AssetCategory | 'all')"
          class="flex items-center gap-1.5 px-3 py-2.5 text-[14px] font-medium whitespace-nowrap"
          :class="activeCategory === cat.key ? 'text-teal-600 border-b-2 border-teal-600' : 'text-slate-500 hover:text-slate-700'"
        >
          <component :is="cat.icon" class="text-lg" />
          {{ cat.label }}
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex gap-1">
      <!-- Asset/Type Tree (Left Panel) -->
      <div class="hidden lg:block w-52 flex-shrink-0">
        <div class="card">
          <!-- Tab Controls -->
          <div class="flex border-b border-slate-100 mb-1">
            <button
              @click="switchTreeView('asset')"
              class="flex-1 py-2 text-sm font-medium text-center"
              :class="treeViewMode === 'asset' ? 'font-bold text-primary border-b-2 border-primary' : 'text-slate-400 hover:text-primary'"
            >
              资产树
            </button>
            <button
              @click="switchTreeView('type')"
              class="flex-1 py-2 text-sm font-medium text-center"
              :class="treeViewMode === 'type' ? 'font-bold text-primary border-b-2 border-primary' : 'text-slate-400 hover:text-primary'"
            >
              类型树
            </button>
          </div>

          <!-- Tree Content -->
          <div class="text-[13px]">
            <template v-if="treeViewMode === 'asset'">
              <!-- Asset Tree - Root Node -->
              <div
                class="py-1 px-2 rounded cursor-pointer hover:bg-slate-50 mb-0.5 font-medium"
                :class="[
                  selectedOrgId === null && isRootExpanded ? 'bg-primary/10 text-primary' : 'text-slate-700',
                  dragOverOrgId === null && draggedOrgId !== null ? 'bg-blue-50' : ''
                ]"
                @click="handleRootClick"
                @contextmenu.prevent.stop="handleOrgContextMenu($event, { id: null, name: 'Default', isRoot: true })"
                @dragover.prevent="handleOrgDragOver($event, null)"
                @dragleave="handleOrgDragLeave"
                @drop.prevent="handleOrgDrop($event, null)"
              >
                <div class="flex items-center gap-1">
                  <DownOutlined v-if="isRootExpanded" class="text-xs cursor-pointer hover:bg-slate-200 rounded p-0.5" />
                  <RightOutlined v-else class="text-xs cursor-pointer hover:bg-slate-200 rounded p-0.5" />
                  <FolderOpenOutlined v-if="isRootExpanded" class="text-sm" />
                  <FolderOutlined v-else class="text-sm" />
                  <span class="flex-1">Default</span>
                  <span class="text-xs text-slate-400">({{ totalAssetCount }})</span>
                </div>
              </div>

              <!-- Child Nodes -->
              <template v-if="isRootExpanded">
                <div
                  v-for="org in flattenedOrgs"
                  :key="org.id"
                  class="py-1 px-2 rounded cursor-pointer hover:bg-slate-50 flex items-center gap-1"
                  :class="{
                    'bg-primary/10 text-primary': selectedOrgId === org.id,
                    'text-slate-600': selectedOrgId !== org.id,
                    'opacity-50': draggedOrgId === org.id,
                    'bg-blue-50 border-t-2 border-primary': dragOverOrgId === org.id
                  }"
                  :style="{ paddingLeft: `${(org.level + 1) * 20 + 8}px` }"
                  @click.stop="handleOrgClick(org)"
                  @contextmenu.prevent.stop="handleOrgContextMenu($event, { id: org.id, name: org.name, isRoot: false })"
                  draggable="true"
                  @dragstart="handleOrgDragStart($event, org.id)"
                  @dragover.prevent="handleOrgDragOver($event, org.id)"
                  @dragleave="handleOrgDragLeave"
                  @drop.prevent="handleOrgDrop($event, org.id)"
                  @dragend="handleOrgDragEnd"
                >
                  <DownOutlined v-if="org.hasChildren && isOrgExpanded(org.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" />
                  <RightOutlined v-else-if="org.hasChildren && !isOrgExpanded(org.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" />
                  <span v-else class="w-3"></span>
                  <FolderOutlined v-if="org.hasChildren && !isOrgExpanded(org.id)" class="text-sm" />
                  <FolderOpenOutlined v-else-if="org.hasChildren && isOrgExpanded(org.id)" class="text-sm" />
                  <FileTextOutlined v-else class="text-sm text-slate-400" />
                  <span class="flex-1 truncate">{{ org.name }}</span>
                  <span class="text-xs text-slate-400">({{ org.count }})</span>
                </div>
              </template>

              <!-- Organization Context Menu -->
              <div
                v-if="showOrgContextMenu"
                class="fixed z-50 bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[140px]"
                :style="{ left: `${orgContextMenuPosition.x}px`, top: `${orgContextMenuPosition.y}px` }"
                @click.stop
              >
                <div
                  v-if="hasPermission('manage')"
                  @click.stop="openCreateOrgModal(orgContextMenuTarget?.id || null)"
                  class="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                >
                  <FolderAddOutlined class="text-sm" />
                  创建节点
                </div>
                <template v-if="orgContextMenuTarget && !orgContextMenuTarget.isRoot">
                  <div
                    v-if="hasPermission('manage')"
                    @click.stop="openRenameOrgModal(orgContextMenuTarget)"
                    class="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                  >
                    <EditOutlined class="text-sm" />
                    重命名节点
                  </div>
                  <div v-if="hasPermission('manage')" class="border-t border-slate-100 my-1"></div>
                  <div
                    v-if="hasPermission('manage')"
                    @click.stop="handleDeleteOrg(orgContextMenuTarget)"
                    class="px-3 py-1.5 text-xs text-red-500 hover:bg-red-50 cursor-pointer flex items-center gap-2"
                  >
                    <DeleteOutlined class="text-sm" />
                    删除节点
                  </div>
                </template>
              </div>
            </template>

            <template v-else-if="treeViewMode === 'type'">
              <!-- Type Tree -->
              <template v-for="node in flattenedTypeTree" :key="node.id">
                <div
                  class="py-1 px-2 rounded cursor-pointer hover:bg-slate-50 flex items-center gap-1"
                  :class="isSelectedTypeNode(node) ? 'bg-primary/10 text-primary' : 'text-slate-600'"
                  :style="{ paddingLeft: `${node.level * 16 + 8}px` }"
                  @click="handleSelectType(node)"
                >
                  <UpOutlined v-if="node.isRoot && expandedTypeIds.includes('all')" class="text-xs cursor-pointer hover:bg-slate-200 rounded" @click.stop="toggleType('all')" />
                  <DownOutlined v-else-if="node.isRoot && !expandedTypeIds.includes('all')" class="text-xs cursor-pointer hover:bg-slate-200 rounded" @click.stop="toggleType('all')" />
                  <UpOutlined v-else-if="node.level === 1 && node.hasChildren && expandedTypeIds.includes(node.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" @click.stop="toggleType(node.id)" />
                  <DownOutlined v-else-if="node.level === 1 && node.hasChildren && !expandedTypeIds.includes(node.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" @click.stop="toggleType(node.id)" />
                  <RightOutlined v-else-if="node.level === 2" class="text-xs" />
                  <span v-else-if="node.level === 1 && !node.hasChildren" class="w-4"></span>
                  <AppstoreOutlined v-if="node.isRoot" class="text-sm mr-1" />
                  <component v-else :is="getCategoryIcon(node.category)" class="text-sm mr-1" />
                  <span class="flex-1 truncate">{{ node.name }}</span>
                </div>
              </template>
            </template>
          </div>
        </div>
      </div>

      <!-- Asset Table (Right Panel) -->
      <div class="flex-1">
        <!-- Action Bar -->
        <div class="bg-white rounded-xl shadow-sm p-2.5 mb-0.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <button v-if="hasPermission('manage')" @click="openCreateModal" class="btn-primary text-xs px-3 py-1.5">创建</button>
              <Dropdown v-if="hasPermission('manage')" :trigger="['click']">
                <button class="border border-slate-300 text-slate-600 text-xs px-3 py-1.5 rounded hover:bg-slate-50 flex items-center gap-1">
                  更多操作 <DownOutlined class="text-[10px]" />
                </button>
                <template #overlay>
                  <div class="bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[140px]">
                    <div class="px-3 py-1 text-xs text-slate-400 font-medium">修改状态</div>
                    <div v-for="s in statusOptions" :key="s.key" @click="bulkUpdateStatus(s.key, fetchData)" class="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2">
                      <span>{{ s.label }}</span>
                    </div>
                    <div class="border-t border-slate-100 my-1"></div>
                    <div @click="selectedCount > 0 && bulkDelete(fetchData, fetchOrganizations)" class="px-3 py-1.5 text-xs text-red-500 hover:bg-red-50 cursor-pointer flex items-center gap-2">
                      <DeleteOutlined class="text-sm" />批量删除
                      <span v-if="selectedCount > 0" class="text-xs text-slate-400 ml-auto">({{ selectedCount }})</span>
                    </div>
                  </div>
                </template>
              </Dropdown>
            </div>
            <div class="flex items-center gap-2">
              <a-input v-model:value="searchQuery" placeholder="搜索资产名称 / 地址 / 编号" size="small" style="width: 320px" @press-enter="handleSearch">
                <template #prefix><SearchOutlined class="text-slate-400" /></template>
                <template #suffix>
                  <button @click="handleSearch" class="p-1 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="搜索"><SearchOutlined class="text-sm" /></button>
                  <button @click="searchQuery = ''; handleSearch()" class="p-1 text-slate-400 hover:text-red-500 hover:bg-slate-100 rounded" title="清空"><CloseOutlined class="text-sm" /></button>
                </template>
              </a-input>
              <select v-model="statusFilter" class="input-field" style="width: 130px; padding: 4px 8px; font-size: 12px" @change="onStatusFilterChange">
                <option value="">全部状态</option>
                <option v-for="s in statusOptions" :key="s.key" :value="s.key">{{ s.label }}</option>
              </select>
              <button @click="showColumnCustomizer = true" class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="自定义列"><SettingOutlined class="text-sm" /></button>
              <button v-if="hasPermission('manage') && activeCategory !== 'all'" @click="showImportModal = true" class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="导入"><ImportOutlined class="text-sm" /></button>
              <button v-if="hasPermission('manage')" @click="showExportModal = true" class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="导出"><ExportOutlined class="text-sm" /></button>
              <button @click="handleSearch" class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="刷新"><ReloadOutlined class="text-sm" /></button>
            </div>
          </div>
        </div>

        <!-- Table -->
        <div class="bg-white rounded-xl shadow-sm overflow-hidden relative">
          <div class="overflow-x-auto" :key="columnConfigVersion">
            <table class="data-table min-w-[1400px]">
              <thead>
                <tr>
                  <template v-for="key in orderedColumns" :key="key">
                    <th v-if="isColVisible(key)"
                        :class="{ 'w-10': key === 'checkbox', 'col-drag-over': !FIXED_COLS.has(key) && dragOverKey === key }"
                        :draggable="!FIXED_COLS.has(key) || undefined"
                        @dragstart="!FIXED_COLS.has(key) ? handleColDragStart(key, $event) : undefined"
                        @dragover="!FIXED_COLS.has(key) ? handleColDragOver(key, $event) : undefined"
                        @dragleave="dragOverKey = ''"
                        @drop="!FIXED_COLS.has(key) ? handleColDrop(key, $event) : undefined"
                        @dragend="handleColDragEnd">
                      <input v-if="key === 'checkbox'" type="checkbox" class="rounded border-gray-300 w-3.5 h-3.5" @change="selectAllChanged($event)" :checked="allSelected" />
                      <template v-else>{{ thLabel(key) }}</template>
                    </th>
                  </template>
                </tr>
              </thead>
              <tbody>
                <tr v-if="assets.length === 0 && !loading"><td :colspan="orderedColumns.filter(k => isColVisible(k)).length" class="text-center py-16 text-slate-400">暂无数据</td></tr>
                <template v-else>
                  <tr v-for="asset in assets" :key="asset.id">
                    <template v-for="key in orderedColumns" :key="key">
                      <td v-if="isColVisible(key)"
                          :class="{ 'text-sm text-slate-600': key === 'applicant', 'whitespace-normal': key === 'notes', 'whitespace-pre-wrap': key === 'address' }">
                        <template v-if="key === 'checkbox'">
                          <input type="checkbox" class="rounded border-gray-300 w-3.5 h-3.5" v-model="asset.selected" @change="selectionChanged" />
                        </template>
                        <template v-else-if="key === 'name'">
                          <p class="font-medium text-slate-900">{{ asset.name }}</p>
                        </template>
                        <template v-else-if="key === 'address'">
                          <!-- All assets show addresses -->
                          <div v-if="asset.external_address" class="text-sm text-slate-600 font-mono">
                            <span class="text-[10px] text-blue-500 font-medium mr-1">外</span>
                            <span v-text="asset.external_address"></span>
                          </div>
                          <div v-if="asset.internal_address" class="text-sm text-slate-600 font-mono">
                            <span class="text-[10px] text-green-500 font-medium mr-1">内</span>
                            <span v-text="asset.internal_address"></span>
                          </div>
                          <span v-if="!asset.external_address && !asset.internal_address" class="text-sm text-slate-400">-</span>
                        </template>
                        <template v-else-if="key === 'asset_code'"><span class="text-sm text-slate-600 font-mono">{{ asset.asset_code || '' }}</span></template>
                        <template v-else-if="key === 'id'"><span class="text-sm text-slate-600 font-mono">{{ asset.id || '' }}</span></template>
                        <template v-else-if="key === 'category'"><span class="text-sm text-slate-600">{{ categoryOptions.find(c => c.key === asset.category)?.label || asset.category }}</span></template>
                        <template v-else-if="key === 'platform'"><span class="text-sm text-slate-600">{{ activeCategory === 'network' ? ((asset.vendor || asset.platform) && asset.model ? `${asset.vendor || asset.platform}/${asset.model}` : (asset.vendor || asset.platform || asset.model || '-')) : (asset.platform || asset.device_type || '-') }}</span></template>
                        <template v-else-if="key === 'device_type'"><span class="text-sm text-slate-600">{{ asset.device_type || '-' }}</span></template>
                        <template v-else-if="key === 'model'"><span class="text-sm text-slate-600">{{ asset.model || '' }}</span></template>
                        <template v-else-if="key === 'serial_number'"><span class="text-sm text-slate-600 font-mono">{{ asset.serial_number || '' }}</span></template>
                        <template v-else-if="key === 'cpu'"><span class="text-sm text-slate-600">{{ asset.cpu || '' }}</span></template>
                        <template v-else-if="key === 'memory'"><span class="text-sm text-slate-600">{{ asset.memory || '' }}</span></template>
                        <template v-else-if="key === 'system_disk'"><span class="text-sm text-slate-600">{{ asset.system_disk || '' }}</span></template>
                        <template v-else-if="key === 'data_disk'"><span class="text-sm text-slate-600">{{ asset.data_disk || '' }}</span></template>
                        <template v-else-if="key === 'oob'">
                          <span class="text-sm text-slate-600 font-mono">{{ asset.oob_address || asset.extra_data?.oob || '' }}</span>
                        </template>
                        <template v-else-if="key === 'oob_credentials'">
                          <div v-if="asset.oob_username || asset.extra_data?.oob_username" class="flex items-center gap-1.5 text-slate-600">
                            <span class="font-medium shrink-0">{{ asset.oob_username || asset.extra_data?.oob_username }}</span>
                            <CopyOutlined class="text-[14px] cursor-pointer hover:text-primary shrink-0" @click="copyUsername(asset.oob_username || asset.extra_data?.oob_username || '')" />
                            <span class="text-slate-400 font-mono ml-1 shrink-0">********</span>
                            <CopyOutlined v-if="hasPermission('view_pwd')" class="text-[14px] cursor-pointer hover:text-primary shrink-0" @click="copyOobPassword(asset)" />
                            <EyeOutlined v-if="hasPermission('view_pwd')" class="text-[14px] cursor-pointer hover:text-primary ml-1 shrink-0" @click.stop="showOobPasswordPopover(asset, $event)" />
                          </div>
                        </template>
                        <template v-else-if="key === 'db_type'"><span class="text-sm text-slate-600">{{ asset.db_type || '' }}</span></template>
                        <template v-else-if="key === 'version'"><span class="text-sm text-slate-600">{{ asset.extra_data?.version || '' }}</span></template>
                        <template v-else-if="key === 'namespace'"><span class="text-sm text-slate-600">{{ asset.namespace || '' }}</span></template>
                        <template v-else-if="key === 'runs_on'">
                          <div v-if="asset.runs_on_hosts?.length" class="flex flex-wrap gap-1">
                            <span v-for="host in asset.runs_on_hosts" :key="host.id" class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-100 text-blue-700">
                              {{ host.name }}
                            </span>
                          </div>
                          <span v-else class="text-sm text-slate-400">-</span>
                        </template>
                        <template v-else-if="key === 'storage_locations'">
                          <div v-if="asset.storage_locations?.length" class="flex flex-wrap gap-1">
                            <span v-for="loc in asset.storage_locations" :key="loc.id" class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-purple-100 text-purple-700" :title="loc.description">
                              <span class="mr-1 text-[9px] opacity-70">{{ loc.path_type }}</span>{{ loc.path }}
                            </span>
                          </div>
                          <span v-else class="text-sm text-slate-400">-</span>
                        </template>
                        <template v-else-if="key === 'organization'"><a-tooltip :title="getOrgPath(asset.organization_id)"><span class="text-sm text-slate-600 cursor-help">{{ asset.organization_name || 'Default' }}</span></a-tooltip></template>
                        <template v-else-if="key === 'status'">
                          <span v-if="asset.status" :class="`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(asset.status)}`">
                            {{ getStatusLabel(asset.status) }}
                          </span>
                          <span v-else class="text-sm text-slate-400">-</span>
                        </template>
                        <template v-else-if="key === 'applicant'">{{ asset.applicant || '' }}</template>
                        <template v-else-if="key === 'owner'"><span class="text-sm text-slate-600">{{ asset.owner_name || '' }}</span></template>
                        <template v-else-if="key === 'credentials'">
                          <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                            <span class="font-medium shrink-0">{{ cred.username }}</span>
                            <CopyOutlined class="text-[14px] cursor-pointer hover:text-primary shrink-0" @click="copyUsername(cred.username)" />
                            <span class="text-slate-400 font-mono ml-1 shrink-0">********</span>
                            <CopyOutlined v-if="hasPermission('view_pwd')" class="text-[14px] cursor-pointer hover:text-primary shrink-0" @click="copyPassword(cred)" />
                            <EyeOutlined v-if="hasPermission('view_pwd')" class="text-[14px] cursor-pointer hover:text-primary ml-1 shrink-0" @click.stop="showPasswordPopover(cred, $event)" />
                          </div>
                        </template>
                        <template v-else-if="key === 'notes'"><span class="text-sm text-slate-600">{{ asset.notes || '' }}</span></template>
                        <template v-else-if="key === 'creator'">
                          <span class="text-sm text-slate-600">{{ asset.creator_name || '-' }}</span>
                        </template>
                        <template v-else-if="key === 'created_at'">
                          <span class="text-sm text-slate-600">{{ formatDateTime(asset.created_at) }}</span>
                        </template>
                        <template v-else-if="key === 'updated_at'">
                          <span class="text-sm text-slate-600">{{ formatDateTime(asset.updated_at) }}</span>
                        </template>
                        <template v-else-if="key === 'actions'">
                          <button v-if="hasPermission('manage')" @click="openEditModal(asset)" class="bg-primary text-white px-2 py-0.5 rounded text-xs">更新</button>
                          <button v-if="hasPermission('manage')" @click="handleDelete(asset, fetchData, fetchOrganizations)" class="border border-red-400 text-red-500 px-2 py-0.5 rounded text-xs ml-1">删除</button>
                        </template>
                      </td>
                    </template>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <!-- Loading overlay -->
          <div v-if="loading && assets.length > 0" class="absolute inset-0 bg-white/50 transition-opacity duration-200 pointer-events-none"></div>
          <div class="px-4 py-2 border-t border-slate-100 flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="flex items-center gap-2 text-sm text-slate-500">
                <span>每页</span>
                <select
                  :value="limit"
                  @change="handleLimitChange(Number(($event.target as HTMLSelectElement).value), fetchData)"
                  class="text-sm border border-slate-200 rounded px-2 py-1 bg-white"
                >
                  <option v-for="size in [15, 30, 50, 100]" :key="size" :value="size">{{ size }}</option>
                </select>
                <span>条</span>
              </div>
              <span class="text-sm text-slate-500">共 {{ total }} 条记录</span>
            </div>
            <div class="flex items-center gap-2">
              <button @click="handlePageChange(page - 1, fetchData)" :disabled="page === 1" class="px-3 py-1.5 text-sm border border-slate-200 rounded disabled:opacity-50">上一页</button>
              <span class="text-sm text-slate-600">{{ page }} / {{ Math.ceil(total / limit) || 1 }}</span>
              <button @click="handlePageChange(page + 1, fetchData)" :disabled="page >= Math.ceil(total / limit)" class="px-3 py-1.5 text-sm border border-slate-200 rounded disabled:opacity-50">下一页</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Column Customizer -->
    <ColumnCustomizer
      v-model:visible="showColumnCustomizer"
      :columns="allColumnsConfig"
      :visibleKeys="visibleColumnKeys"
      @toggle="toggleColumn"
      @reset="resetColumns"
    />

    <!-- Import Modal -->
    <ImportModal
      v-model:visible="showImportModal"
      :category="activeCategory"
      @success="handleImportSuccess"
    />

    <!-- Export Modal -->
    <ExportModal
      v-model:visible="showExportModal"
      :category="activeCategory"
      :selected-ids="selectedIds"
      :search-query="searchQuery"
      :organization-id="selectedOrgId"
    />

    <!-- Create/Edit Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showModal = false"></div>
      <div class="relative bg-white w-full max-w-xl rounded-lg shadow-2xl max-h-[90vh] overflow-y-auto">
        <div class="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-base font-semibold text-slate-900">{{ modalTitle }}</h2>
          <button @click="showModal = false" class="p-1 hover:bg-slate-100 rounded transition-colors">
            <CloseOutlined class="text-slate-400" />
          </button>
        </div>
        <div class="p-3">
          <form @submit.prevent="handleSubmit" autocomplete="off" class="space-y-3">
            <!-- Row 1: 资产名称、资产编号 -->
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">资产名称 <span class="text-red-500">*</span></label>
                <input v-model="form.name" type="text" class="input-field" placeholder="请输入资产名称" />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">资产编号</label>
                <input v-model="form.asset_code" type="text" class="input-field" placeholder="CI编号" />
              </div>
            </div>

            <!-- Row 2: 节点路径 -->
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1">节点</label>
              <select v-model="formSelectedOrgId" class="input-field">
                <option v-for="org in allOrgsForSelect" :key="org.id ?? 'default'" :value="org.id">
                  {{ org.path }}
                </option>
              </select>
            </div>

            <!-- Network设备专用布局 -->
            <template v-if="form.category === 'network'">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">资产类型 <span class="text-red-500">*</span></label>
                  <select v-model="form.category" class="input-field">
                    <option v-for="cat in categoryOptions" :key="cat.key" :value="cat.key">{{ cat.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">设备类型</label>
                  <select v-model="form.device_type" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="t in localDeviceTypeOptions" :key="t" :value="t">{{ t }}</option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">平台</label>
                  <select v-model="form.platform" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="p in platformOptions[form.category]" :key="p" :value="p">{{ p }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">型号</label>
                  <input v-model="form.model" type="text" class="input-field" placeholder="如: C9300-48P" />
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">序列号</label>
                  <input v-model="form.serial_number" type="text" class="input-field" placeholder="设备序列号" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">状态</label>
                  <select v-model="form.status" class="input-field">
                    <option value="">无</option>
                    <option v-for="s in statusOptions" :key="s.key" :value="s.key">{{ s.label }}</option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">外网地址</label>
                  <input v-model="form.external_address" type="text" class="input-field" placeholder="外网 IP 地址" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">内网地址</label>
                  <input v-model="form.internal_address" type="text" class="input-field" placeholder="内网 IP 地址" />
                </div>
              </div>
            </template>

            <!-- 其他类别布局 -->
            <template v-else>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">资产类型 <span class="text-red-500">*</span></label>
                  <select v-model="form.category" class="input-field">
                    <option v-for="cat in categoryOptions" :key="cat.key" :value="cat.key">{{ cat.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">平台</label>
                  <select v-model="form.platform" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="p in platformOptions[form.category]" :key="p" :value="p">{{ p }}</option>
                  </select>
                </div>
              </div>
              <div v-if="form.category === 'database'" class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">数据库类型</label>
                  <select v-model="form.db_type" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="t in dbTypeOptions" :key="t" :value="t">{{ t }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">版本</label>
                  <input v-model="form.version" type="text" class="input-field" placeholder="数据库版本" />
                </div>
              </div>
              <div v-if="form.category === 'database'">
                <label class="block text-xs font-medium text-slate-600 mb-1">命名空间</label>
                <input v-model="form.namespace" type="text" class="input-field" placeholder="命名空间" />
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">外网地址</label>
                  <input v-model="form.external_address" type="text" class="input-field" :placeholder="['cloud','web','gpt'].includes(form.category) ? 'https://example.com' : '外网 IP 地址'" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">内网地址</label>
                  <input v-model="form.internal_address" type="text" class="input-field" :placeholder="['cloud','web','gpt'].includes(form.category) ? 'https://internal.example.com' : '内网 IP 地址'" />
                </div>
              </div>
            </template>

            <!-- 用户名密码区域 -->
            <div class="bg-slate-50 rounded-lg">
              <div class="px-3 py-2 border-b border-slate-200">
                <span class="text-xs font-medium text-slate-600">用户名密码</span>
              </div>
              <div class="p-3">
                <!-- 已有凭证列表 -->
                <div v-if="formCredentials.length > 0" class="space-y-1 mb-1">
                  <div v-for="(cred, index) in formCredentials" :key="index" class="bg-slate-50 px-3 py-2 rounded-lg border border-slate-200">
                    <div class="flex items-center gap-3">
                      <!-- 用户名字段 -->
                      <div class="flex items-center gap-2 flex-1">
                        <span class="text-xs text-slate-500">用户名:</span>
                        <input
                          v-if="isFieldEditing(index, 'username')"
                          :ref="(el: any) => { if (el) credentialInputRefs.set(`${index}-username`, el) }"
                          v-model="cred.username"
                          type="text"
                          class="input-field text-xs flex-1"
                          autocomplete="off"
                          @blur="stopFieldEdit"
                          @keyup.enter.prevent="stopFieldEdit"
                        />
                        <span
                          v-else
                          class="font-medium text-slate-700 cursor-pointer hover:bg-slate-200 px-1 rounded"
                          @dblclick="startFieldEdit(index, 'username')"
                          title="双击编辑"
                        >{{ cred.username }}</span>
                      </div>
                      <!-- 密码字段 -->
                      <div class="flex items-center gap-2 flex-1">
                        <span class="text-xs text-slate-500">密码:</span>
                        <input
                          v-if="isFieldEditing(index, 'password')"
                          :ref="(el: any) => { if (el) credentialInputRefs.set(`${index}-password`, el) }"
                          v-model="cred.password"
                          type="text"
                          class="input-field text-xs flex-1"
                          autocomplete="off"
                          @blur="stopFieldEdit"
                          @keyup.enter.prevent="stopFieldEdit"
                          placeholder="输入新密码"
                        />
                        <span
                          v-else-if="cred.id && decryptedFormPasswords.has(cred.id)"
                          class="text-slate-700 font-mono cursor-pointer hover:bg-slate-200 px-1 rounded"
                          @dblclick="startFieldEdit(index, 'password')"
                          title="双击编辑"
                        >{{ decryptedFormPasswords.get(cred.id) }}</span>
                        <span
                          v-else-if="!cred.id && visibleNewPasswords.has(index)"
                          class="text-slate-700 font-mono cursor-pointer hover:bg-slate-200 px-1 rounded"
                          @dblclick="startFieldEdit(index, 'password')"
                          title="双击编辑"
                        >{{ cred.password }}</span>
                        <span
                          v-else
                          class="text-slate-400 font-mono cursor-pointer hover:bg-slate-200 px-1 rounded"
                          @dblclick="startFieldEdit(index, 'password')"
                          title="双击编辑"
                        >********</span>
                      </div>
                      <!-- 操作按钮 -->
                      <div class="flex items-center gap-0.5">
                        <button v-if="cred.id && hasPermission('view_pwd')" type="button" @click="viewFormCredentialPassword(cred)" class="p-1.5 text-slate-400 hover:text-primary hover:bg-slate-100 rounded" :title="decryptedFormPasswords.has(cred.id) ? '隐藏密码' : '查看密码'">
                          <EyeOutlined v-if="!decryptedFormPasswords.has(cred.id)" class="text-sm" />
                          <EyeInvisibleOutlined v-else class="text-sm" />
                        </button>
                        <button v-else type="button" @click="viewFormCredentialPassword(cred, index)" class="p-1.5 text-slate-400 hover:text-primary hover:bg-slate-100 rounded" :title="visibleNewPasswords.has(index) ? '隐藏密码' : '查看密码'">
                          <EyeOutlined v-if="!visibleNewPasswords.has(index)" class="text-sm" />
                          <EyeInvisibleOutlined v-else class="text-sm" />
                        </button>
                        <button type="button" @click="removeCredentialFromForm(index)" class="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded" title="删除">
                          <DeleteOutlined class="text-sm" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- 添加新凭证 -->
                <div class="flex items-end gap-2">
                  <div class="flex-1">
                    <label class="block text-xs text-slate-500 mb-1">用户名</label>
                    <input
                      v-model="newCredentialForm.username"
                      type="text"
                      class="input-field text-sm"
                      placeholder="输入用户名"
                      autocomplete="off"
                      @keyup.enter.prevent="addCredentialToForm"
                    />
                  </div>
                  <div class="flex-1 relative">
                    <label class="block text-xs text-slate-500 mb-1">密码</label>
                    <input
                      v-model="newCredentialForm.password"
                      :type="showPassword ? 'text' : 'password'"
                      class="input-field text-sm w-full pr-8"
                      placeholder="输入密码"
                      autocomplete="off"
                      @keyup.enter.prevent="addCredentialToForm"
                    />
                    <button type="button" @click="showPassword = !showPassword" class="absolute right-2 top-[calc(50%+10px)] -translate-y-1/2 text-slate-400 hover:text-slate-600">
                      <EyeOutlined v-if="!showPassword" class="text-sm" />
                      <EyeInvisibleOutlined v-else class="text-sm" />
                    </button>
                  </div>
                  <button
                    type="button"
                    @click="addCredentialToForm"
                    class="bg-primary text-white px-3 py-1.5 rounded text-sm hover:bg-blue-600 transition-colors h-8"
                  >
                    <PlusCircleOutlined class="mr-1" /> 添加
                  </button>
                </div>
              </div>
            </div>

            <!-- Network 专属字段 -->
            <template v-if="form.category === 'network'">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">申请人</label>
                  <input v-model="form.applicant" type="text" class="input-field" placeholder="申请人姓名" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">负责人</label>
                  <select v-model="form.owner_id" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="user in userOptions" :key="user.id" :value="user.id">
                      {{ user.username }}
                    </option>
                  </select>
                </div>
              </div>
            </template>

            <!-- Web 专属字段 -->
            <template v-if="form.category === 'web'">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">状态</label>
                  <select v-model="form.status" class="input-field">
                    <option value="">无</option>
                    <option v-for="s in statusOptions" :key="s.key" :value="s.key">{{ s.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">申请人</label>
                  <input v-model="form.applicant" type="text" class="input-field" placeholder="申请人姓名" />
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">负责人</label>
                <select v-model="form.owner_id" class="input-field">
                  <option value="">请选择</option>
                  <option v-for="user in userOptions" :key="user.id" :value="user.id">
                    {{ user.username }}
                  </option>
                </select>
              </div>
            </template>

            <!-- 数据库专属字段 -->
            <template v-if="form.category === 'database'">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">状态</label>
                  <select v-model="form.status" class="input-field">
                    <option value="">无</option>
                    <option v-for="s in statusOptions" :key="s.key" :value="s.key">{{ s.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">申请人</label>
                  <input v-model="form.applicant" type="text" class="input-field" placeholder="申请人姓名" />
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">负责人</label>
                <select v-model="form.owner_id" class="input-field">
                  <option value="">请选择</option>
                  <option v-for="user in userOptions" :key="user.id" :value="user.id">
                    {{ user.username }}
                  </option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">运行于主机</label>
                <Select
                  v-model:value="form.host_ids"
                  mode="multiple"
                  :allow-clear="true"
                  :max-tag-count="2"
                  :options="filteredHostOptions.map(h => ({ label: `${h.name} (${h.internal_address || '无地址'})`, value: h.id }))"
                  :filter-option="false"
                  @search="onHostSearch"
                  placeholder="搜索主机名或IP"
                  style="width: 100%"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-2">存储位置</label>
                <div v-for="(loc, idx) in form.storage_locations" :key="idx" class="flex gap-2 mb-2 items-start">
                  <input v-model="loc.path" type="text" class="input-field flex-1 text-xs" placeholder="路径" />
                  <select v-model="loc.path_type" class="input-field w-24 text-xs">
                    <option value="data">数据</option>
                    <option value="log">日志</option>
                    <option value="backup">备份</option>
                    <option value="temp">临时</option>
                  </select>
                  <input v-model="loc.description" type="text" class="input-field flex-1 text-xs" placeholder="描述" />
                  <button type="button" @click="form.storage_locations.splice(idx, 1)" class="p-1.5 text-slate-400 hover:text-red-500 rounded mt-0">
                    <DeleteOutlined class="text-xs" />
                  </button>
                </div>
                <button type="button" @click="form.storage_locations.push({ path: '', path_type: 'data', description: '' })" class="text-xs text-primary hover:underline flex items-center gap-1">
                  <PlusCircleOutlined class="text-xs" /> 添加存储位置
                </button>
              </div>
            </template>

            <!-- Cloud 专属字段 -->
            <template v-if="form.category === 'cloud'">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">状态</label>
                  <select v-model="form.status" class="input-field">
                    <option value="">无</option>
                    <option v-for="s in statusOptions" :key="s.key" :value="s.key">{{ s.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">负责人</label>
                  <select v-model="form.owner_id" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="user in userOptions" :key="user.id" :value="user.id">
                      {{ user.username }}
                    </option>
                  </select>
                </div>
              </div>
            </template>

            <!-- GPT 专属字段 -->
            <template v-if="form.category === 'gpt'">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">状态</label>
                  <select v-model="form.status" class="input-field">
                    <option value="">无</option>
                    <option v-for="s in statusOptions" :key="s.key" :value="s.key">{{ s.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">负责人</label>
                  <select v-model="form.owner_id" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="user in userOptions" :key="user.id" :value="user.id">
                      {{ user.username }}
                    </option>
                  </select>
                </div>
              </div>
            </template>

            <!-- 主机专属字段 -->
            <template v-if="form.category === 'host'">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">型号</label>
                  <input v-model="form.model" type="text" class="input-field" placeholder="设备型号" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">序列号</label>
                  <input v-model="form.serial_number" type="text" class="input-field" placeholder="序列号" />
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">CPU</label>
                  <input v-model="form.cpu" type="text" class="input-field" placeholder="如: 8核" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">内存</label>
                  <input v-model="form.memory" type="text" class="input-field" placeholder="如: 16GB" />
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">系统盘</label>
                  <input v-model="form.system_disk" type="text" class="input-field" placeholder="如: 500GB SSD" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">数据盘</label>
                  <input v-model="form.data_disk" type="text" class="input-field" placeholder="如: 2TB HDD" />
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">OOB</label>
                <input v-model="form.oob" type="text" class="input-field" placeholder="带外管理地址" />
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">OOB用户名</label>
                  <input v-model="form.oob_username" type="text" class="input-field" placeholder="OOB 用户名" autocomplete="off" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">OOB密码</label>
                  <div class="relative">
                    <input v-model="form.oob_password" :type="showOobPassword ? 'text' : 'password'" class="input-field pr-8" placeholder="OOB 密码" autocomplete="off" />
                    <button type="button" @click="showOobPassword = !showOobPassword" class="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                      <EyeOutlined v-if="!showOobPassword" class="text-sm" />
                      <EyeInvisibleOutlined v-else class="text-sm" />
                    </button>
                  </div>
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">状态</label>
                <select v-model="form.status" class="input-field">
                  <option value="">无</option>
                  <option v-for="s in statusOptions" :key="s.key" :value="s.key">{{ s.label }}</option>
                </select>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">申请人</label>
                  <input v-model="form.applicant" type="text" class="input-field" placeholder="申请人姓名" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1">负责人</label>
                  <select v-model="form.owner_id" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="user in userOptions" :key="user.id" :value="user.id">
                      {{ user.username }}
                    </option>
                  </select>
                </div>
              </div>
            </template>

            <!-- 描述 -->
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1">描述</label>
              <textarea v-model="form.notes" class="input-field h-20 resize-none" placeholder="资产描述或备注"></textarea>
            </div>

            <!-- 操作按钮 -->
            <div class="flex justify-end gap-3 pt-1.5 border-t border-slate-100">
              <button type="button" @click="showModal = false" class="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors">
                取消
              </button>
              <button type="submit" :disabled="modalLoading" class="btn-primary" autocomplete="off">
                {{ modalLoading ? '处理中...' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Organization Modal -->
    <div v-if="showOrgModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showOrgModal = false"></div>
      <div class="relative bg-white w-full max-w-md rounded-xl shadow-2xl">
        <div class="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-lg font-bold text-slate-900">{{ orgModalMode === 'create' ? '创建节点' : '重命名节点' }}</h2>
          <button @click="showOrgModal = false" class="p-1.5 hover:bg-slate-100 rounded-lg"><CloseOutlined class="text-slate-400" /></button>
        </div>
        <div class="p-4">
          <div class="space-y-4">
            <div><label class="block text-xs font-medium text-slate-600 mb-1">节点名称 <span class="text-red-500">*</span></label><input v-model="orgForm.name" type="text" class="input-field" placeholder="请输入节点名称" autofocus @keydown.enter="handleOrgModalSubmit" /></div>
            <div class="flex justify-end gap-3 pt-1.5 border-t border-slate-100">
              <button type="button" @click="showOrgModal = false" class="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg">取消</button>
              <button type="button" @click="handleOrgModalSubmit" :disabled="orgModalLoading" class="btn-primary">{{ orgModalLoading ? '处理中...' : '确定' }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>