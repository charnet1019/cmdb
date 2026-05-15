<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Dropdown } from 'ant-design-vue'
import {
  DownOutlined,
  UpOutlined,
  RightOutlined,
  DeleteOutlined,
  CloseOutlined,
  StopOutlined,
  CheckCircleOutlined,
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
  ImportOutlined
} from '@ant-design/icons-vue'
import { useAssets } from './composables/useAssets'
import { useOrganizations } from './composables/useOrganizations'
import { useCredentials } from './composables/useCredentials'
import { useTypeTree, categories, platformOptions, categoryOptions, dbTypeOptions } from './composables/useTypeTree'
import { useColumnConfig } from './composables/useColumnConfig'
import { createAsset, updateAsset, createCredential, updateCredential } from '@/api/assets'
import { getUsers } from '@/api/users'
import ColumnCustomizer from './components/ColumnCustomizer.vue'
import ImportModal from './components/ImportModal.vue'
import ExportModal from './components/ExportModal.vue'
import type { Asset, AssetCategory } from '@/types'

// Format datetime: treat naive ISO strings as UTC, then convert to local timezone (UTC+8)
function formatDateTime(isoString?: string | null): string {
  if (!isoString) return ''
  try {
    // If string has no timezone info, treat it as UTC by appending +00:00
    const normalized = isoString.match(/[+-]\d{2}:\d{2}$|Z$/) ? isoString : isoString + '+00:00'
    const date = new Date(normalized)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).replace(/\//g, '-')
  } catch {
    return isoString
  }
}

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
  selectedActiveCount,
  selectedInactiveCount,
  selectedIds,
  canDisable,
  canActivate,
  fetchAssets,
  fetchAssetStats,
  handlePageChange,
  selectAllChanged,
  selectionChanged,
  bulkDisable,
  bulkActivate,
  bulkDelete,
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
  handleOrgDragEnd
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
  viewPassword,
  viewFormCredentialPassword,
  addCredentialToForm,
  removeCredentialFromForm,
  startFieldEdit,
  stopFieldEdit,
  isFieldEditing,
  resetFormCredentials
} = useCredentials()

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

function showOobPasswordPopover(asset: any, event: MouseEvent) {
  const password = asset.extra_data?.oob_password
  if (!password) return
  if (passwordPopover.value?.credId === -asset.id) {
    passwordPopover.value = null
    return
  }
  const rect = (event.target as HTMLElement).getBoundingClientRect()
  passwordPopover.value = { credId: -asset.id, password, x: rect.left, y: rect.top }
}

// Tree view mode
const treeViewMode = ref<'asset' | 'type'>('asset')

// Search
const searchQuery = ref('')

// Modal
const showModal = ref(false)
const showPassword = ref(false)
const showOobPassword = ref(false)
const modalLoading = ref(false)
const editingAsset = ref<Asset | null>(null)
const formSelectedOrgId = ref<number | null>(null)

// Device type options for network
const localDeviceTypeOptions = ['交换机', '路由器', '防火墙', '负载均衡', '无线控制器']

// User list for owner selection
const userOptions = ref<Array<{ id: number; username: string; full_name: string | null }>>([])
const loadingUsers = ref(false)

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

// Form
const form = ref({
  name: '',
  asset_code: '',
  category: 'host' as AssetCategory,
  internal_address: '',
  external_address: '',
  platform: '',
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
  notes: ''
})

// Modal title
const modalTitle = computed(() => editingAsset.value ? '编辑资产' : '创建资产')
// Fetch data function
function fetchData() {
  fetchAssets({
    category: activeCategory.value,
    search: searchQuery.value,
    organizationId: selectedOrgId.value
  })
}

// Handle search
function handleSearch() {
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
    updateUrlState({ tree: 'type', type: 'all' })
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
    updateUrlState({ tree: 'type', type: category })
  }
  page.value = 1
  fetchData()
}

// Handle root click - select root and refresh assets
function handleRootClick() {
  selectedOrgId.value = null
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
    notes: ''
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
  showModal.value = true
}

// Open edit modal
async function openEditModal(asset: Asset) {
  editingAsset.value = asset
  form.value = {
    name: asset.name,
    asset_code: asset.asset_code || '',
    category: asset.category,
    internal_address: asset.internal_address || '',
    external_address: asset.external_address || '',
    platform: asset.platform || '',
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
    oob: asset.extra_data?.oob || '',
    oob_username: asset.extra_data?.oob_username || '',
    oob_password: asset.extra_data?.oob_password || '',
    applicant: asset.applicant || '',
    owner_id: asset.owner_id || null,
    notes: asset.notes || ''
  }
  formSelectedOrgId.value = asset.organization_id || null
  formCredentials.value = (asset.credentials || []).map(c => ({
    id: c.id,
    username: c.username,
    password: ''
  }))
  await loadUsers()
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
    // Prepare extra_data for host and database assets
    let extraData: Record<string, any> | undefined
    if (form.value.category === 'host' || form.value.category === 'database') {
      const extraFields: Record<string, any> = {}
      // Host oob fields (applicant now goes to independent column)
      if (form.value.category === 'host') {
        if (form.value.oob) extraFields.oob = form.value.oob
        if (form.value.oob_username) extraFields.oob_username = form.value.oob_username
        if (form.value.oob_password) extraFields.oob_password = form.value.oob_password
      }
      // Database version field (db_type, namespace, applicant now go to independent columns)
      if (form.value.category === 'database') {
        if (form.value.version) extraFields.version = form.value.version
      }
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
      extra_data: extraData,
      notes: form.value.notes || undefined,
      organization_id: formSelectedOrgId.value || undefined
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
  <div class="space-y-4" @click="closePasswordPopover">
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
          class="flex items-center gap-2 px-6 py-4 text-sm font-medium whitespace-nowrap"
          :class="activeCategory === cat.key ? 'text-teal-600 border-b-2 border-teal-600' : 'text-slate-500 hover:text-slate-700'"
        >
          <component :is="cat.icon" class="text-lg" />
          {{ cat.label }}
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex gap-6">
      <!-- Asset/Type Tree (Left Panel) -->
      <div class="hidden lg:block w-60 flex-shrink-0">
        <div class="card">
          <!-- Tab Controls -->
          <div class="flex border-b border-slate-100 mb-1">
            <button
              @click="switchTreeView('asset')"
              class="flex-1 py-2 text-xs font-medium text-center"
              :class="treeViewMode === 'asset' ? 'font-bold text-primary border-b-2 border-primary' : 'text-slate-400 hover:text-primary'"
            >
              资产树
            </button>
            <button
              @click="switchTreeView('type')"
              class="flex-1 py-2 text-xs font-medium text-center"
              :class="treeViewMode === 'type' ? 'font-bold text-primary border-b-2 border-primary' : 'text-slate-400 hover:text-primary'"
            >
              类型树
            </button>
          </div>

          <!-- Tree Content -->
          <div class="text-sm">
            <template v-if="treeViewMode === 'asset'">
              <!-- Asset Tree - Root Node -->
              <div
                class="py-2 px-2 rounded cursor-pointer hover:bg-slate-50 mb-1 font-medium"
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
                  class="py-1.5 px-2 rounded cursor-pointer hover:bg-slate-50 flex items-center gap-1"
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
                  @click.stop="openCreateOrgModal(orgContextMenuTarget?.id || null)"
                  class="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                >
                  <FolderAddOutlined class="text-sm" />
                  创建节点
                </div>
                <template v-if="orgContextMenuTarget && !orgContextMenuTarget.isRoot">
                  <div
                    @click.stop="openRenameOrgModal(orgContextMenuTarget)"
                    class="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                  >
                    <EditOutlined class="text-sm" />
                    重命名节点
                  </div>
                  <div class="border-t border-slate-100 my-1"></div>
                  <div
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
                  class="py-1.5 px-2 rounded cursor-pointer hover:bg-slate-50 flex items-center gap-1"
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
        <div class="bg-white rounded-xl shadow-sm p-3 mb-1">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <button @click="openCreateModal" class="btn-primary text-xs px-3 py-1.5">创建</button>
              <Dropdown :trigger="['click']">
                <button class="border border-slate-300 text-slate-600 text-xs px-3 py-1.5 rounded hover:bg-slate-50 flex items-center gap-1">
                  更多操作 <DownOutlined class="text-[10px]" />
                </button>
                <template #overlay>
                  <div class="bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[140px]">
                    <div @click="canDisable && bulkDisable(fetchData)" class="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2" :class="!canDisable ? 'opacity-50 cursor-not-allowed' : ''">
                      <StopOutlined class="text-sm" />批量禁用
                      <span v-if="selectedActiveCount > 0" class="text-xs text-slate-400 ml-auto">({{ selectedActiveCount }})</span>
                    </div>
                    <div @click="canActivate && bulkActivate(fetchData)" class="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2" :class="!canActivate ? 'opacity-50 cursor-not-allowed' : ''">
                      <CheckCircleOutlined class="text-sm" />批量激活
                      <span v-if="selectedInactiveCount > 0" class="text-xs text-slate-400 ml-auto">({{ selectedInactiveCount }})</span>
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
              <input v-model="searchQuery" type="text" placeholder="搜索" class="border border-gray-200 rounded py-1.5 px-3 text-xs w-72" @keyup.enter="handleSearch" />
              <button @click="showColumnCustomizer = true" class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="自定义列"><SettingOutlined class="text-sm" /></button>
              <button v-if="activeCategory !== 'all'" @click="showImportModal = true" class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="导入"><ImportOutlined class="text-sm" /></button>
              <button @click="showExportModal = true" class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="导出"><ExportOutlined class="text-sm" /></button>
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
                        :class="{ 'w-10': key === 'checkbox', 'text-right': key === 'actions', 'col-drag-over': !FIXED_COLS.has(key) && dragOverKey === key }"
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
                  <tr v-for="asset in assets" :key="asset.id" :class="{ 'opacity-50 bg-slate-50': !asset.is_active }">
                    <template v-for="key in orderedColumns" :key="key">
                      <td v-if="isColVisible(key)"
                          :class="{ 'text-right': key === 'actions', 'text-sm text-slate-600': key === 'applicant', 'whitespace-normal': key === 'notes', 'whitespace-pre-wrap': key === 'address' }">
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
                        <template v-else-if="key === 'oob'"><span class="text-sm text-slate-600 font-mono">{{ asset.extra_data?.oob || '' }}</span></template>
                        <template v-else-if="key === 'oob_credentials'">
                          <div v-if="asset.extra_data?.oob_username" class="flex items-center gap-1.5 text-slate-600">
                            <span class="font-medium shrink-0">{{ asset.extra_data.oob_username }}</span>
                            <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary shrink-0" @click="copyUsername(asset.extra_data.oob_username)" />
                            <span class="text-slate-400 font-mono ml-1 shrink-0">********</span>
                            <CopyOutlined v-if="asset.is_active && asset.extra_data?.oob_password" class="text-[14px] cursor-pointer hover:text-primary shrink-0" @click="copyUsername(asset.extra_data.oob_password)" />
                            <EyeOutlined v-if="asset.is_active && asset.extra_data?.oob_password" class="text-[14px] cursor-pointer hover:text-primary ml-1 shrink-0" @click.stop="showOobPasswordPopover(asset, $event)" />
                          </div>
                        </template>
                        <template v-else-if="key === 'db_type'"><span class="text-sm text-slate-600">{{ asset.db_type || '' }}</span></template>
                        <template v-else-if="key === 'version'"><span class="text-sm text-slate-600">{{ asset.extra_data?.version || '' }}</span></template>
                        <template v-else-if="key === 'namespace'"><span class="text-sm text-slate-600">{{ asset.namespace || '' }}</span></template>
                        <template v-else-if="key === 'organization'"><span class="text-sm text-slate-600">{{ asset.organization_name || 'Default' }}</span></template>
                        <template v-else-if="key === 'is_active'">
                          <span v-if="asset.is_active" class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">启用</span>
                          <span v-else class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">禁用</span>
                        </template>
                        <template v-else-if="key === 'applicant'">{{ asset.applicant || '' }}</template>
                        <template v-else-if="key === 'owner'"><span class="text-sm text-slate-600">{{ asset.owner_name || '' }}</span></template>
                        <template v-else-if="key === 'credentials'">
                          <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                            <span class="font-medium shrink-0">{{ cred.username }}</span>
                            <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary shrink-0" @click="copyUsername(cred.username)" />
                            <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed shrink-0" />
                            <span class="text-slate-400 font-mono ml-1 shrink-0">********</span>
                            <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary shrink-0" @click="copyPassword(cred)" />
                            <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed shrink-0" />
                            <EyeOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary ml-1 shrink-0" @click.stop="showPasswordPopover(cred, $event)" />
                            <EyeOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed ml-1 shrink-0" />
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
                          <button v-if="asset.is_active" @click="openEditModal(asset)" class="bg-primary text-white px-2 py-0.5 rounded text-xs">更新</button>
                          <button v-else disabled class="bg-slate-200 text-slate-400 px-2 py-0.5 rounded cursor-not-allowed text-xs">更新</button>
                          <button v-if="asset.is_active" @click="handleDelete(asset, fetchData, fetchOrganizations)" class="border border-red-400 text-red-500 px-2 py-0.5 rounded text-xs ml-1">删除</button>
                          <button v-else disabled class="border border-slate-200 text-slate-300 px-2 py-0.5 rounded cursor-not-allowed text-xs ml-1">删除</button>
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
          <div class="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
            <span class="text-sm text-slate-500">共 {{ total }} 条记录</span>
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
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">序列号</label>
                <input v-model="form.serial_number" type="text" class="input-field" placeholder="设备序列号" />
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
                        <button v-if="cred.id" type="button" @click="viewFormCredentialPassword(cred)" class="p-1.5 text-slate-400 hover:text-primary hover:bg-slate-100 rounded" :title="decryptedFormPasswords.has(cred.id) ? '隐藏密码' : '查看密码'">
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

            <!-- Web 专属字段 -->
            <template v-if="form.category === 'web'">
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

            <!-- 数据库专属字段 -->
            <template v-if="form.category === 'database'">
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

            <!-- Cloud 专属字段 -->
            <template v-if="form.category === 'cloud'">
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

            <!-- GPT 专属字段 -->
            <template v-if="form.category === 'gpt'">
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
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-lg font-bold text-slate-900">{{ orgModalMode === 'create' ? '创建节点' : '重命名节点' }}</h2>
          <button @click="showOrgModal = false" class="p-1.5 hover:bg-slate-100 rounded-lg"><CloseOutlined class="text-slate-400" /></button>
        </div>
        <div class="p-6">
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