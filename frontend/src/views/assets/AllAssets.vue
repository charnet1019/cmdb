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
import { useTypeTree, categories, platformOptions, categoryOptions, deviceTypeOptions, dbTypeOptions } from './composables/useTypeTree'
import { useColumnConfig } from './composables/useColumnConfig'
import { createAsset, updateAsset, createCredential, updateCredential } from '@/api/assets'
import ColumnCustomizer from './components/ColumnCustomizer.vue'
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
  selectedActiveCount,
  selectedInactiveCount,
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
  toggleColumn,
  resetColumns
} = useColumnConfig(activeCategory)
const showColumnCustomizer = ref(false)

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

// Tree view mode
const treeViewMode = ref<'asset' | 'type'>('asset')

// Search
const searchQuery = ref('')

// Modal
const showModal = ref(false)
const showPassword = ref(false)
const modalLoading = ref(false)
const editingAsset = ref<Asset | null>(null)
const formSelectedOrgId = ref<number | null>(null)

// Device type options for network
const deviceTypeOptions = ['交换机', '路由器', '防火墙', '负载均衡', '无线控制器']

// Form
const form = ref({
  name: '',
  asset_code: '',
  category: 'host' as AssetCategory,
  address: '',
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
  url: '',
  version: '',
  namespace: '',
  db_type: activeCategory.value === 'database' ? 'MySQL' : '',
  applicant: '',
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
function openCreateModal() {
  editingAsset.value = null
  form.value = {
    name: '',
    asset_code: '',
    category: activeCategory.value !== 'all' ? activeCategory.value : 'host',
    address: '',
    internal_address: '',
    external_address: '',
    platform: activeCategory.value === 'database' ? 'Kubernetes' : '',
    device_type: '',
    model: '',
    serial_number: '',
    cpu: '',
    memory: '',
    system_disk: '',
    data_disk: '',
    url: '',
    version: '',
    namespace: '',
    db_type: activeCategory.value === 'database' ? 'MySQL' : '',
    applicant: '',
    notes: ''
  }
  formSelectedOrgId.value = selectedOrgId.value

  // Auto-fill based on selected type tree node
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

  resetFormCredentials()
  showModal.value = true
}

// Open edit modal
function openEditModal(asset: Asset) {
  editingAsset.value = asset
  form.value = {
    name: asset.name,
    asset_code: asset.asset_code || '',
    category: asset.category,
    address: asset.address || '',
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
    url: asset.url || '',
    version: asset.extra_data?.version || '',
    namespace: asset.extra_data?.namespace || '',
    db_type: asset.extra_data?.db_type || '',
    applicant: asset.extra_data?.applicant || '',
    notes: asset.notes || ''
  }
  formSelectedOrgId.value = asset.organization_id || null
  formCredentials.value = (asset.credentials || []).map(c => ({
    id: c.id,
    username: c.username,
    password: ''
  }))
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
      // Host applicant
      if (form.value.category === 'host' && form.value.applicant) {
        extraFields.applicant = form.value.applicant
      }
      // Database fields
      if (form.value.category === 'database') {
        if (form.value.db_type) extraFields.db_type = form.value.db_type
        if (form.value.version) extraFields.version = form.value.version
        if (form.value.namespace) extraFields.namespace = form.value.namespace
        if (form.value.applicant) extraFields.applicant = form.value.applicant
      }
      extraData = Object.keys(extraFields).length > 0 ? extraFields : undefined
    }

    const data = {
      name: form.value.name,
      asset_code: form.value.asset_code || undefined,
      category: form.value.category,
      address: form.value.address || undefined,
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
      url: form.value.url || undefined,
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
          <div class="flex border-b border-slate-100 mb-4">
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
                  class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                >
                  <FolderAddOutlined class="text-sm" />
                  创建节点
                </div>
                <template v-if="orgContextMenuTarget && !orgContextMenuTarget.isRoot">
                  <div
                    @click.stop="openRenameOrgModal(orgContextMenuTarget)"
                    class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                  >
                    <EditOutlined class="text-sm" />
                    重命名节点
                  </div>
                  <div class="border-t border-slate-100 my-1"></div>
                  <div
                    @click.stop="handleDeleteOrg(orgContextMenuTarget)"
                    class="px-4 py-2 text-sm text-red-500 hover:bg-red-50 cursor-pointer flex items-center gap-2"
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
        <div class="bg-white rounded-xl shadow-sm p-3 mb-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <button @click="openCreateModal" class="btn-primary text-xs px-3 py-1.5">创建</button>
              <Dropdown :trigger="['click']">
                <button class="border border-slate-300 text-slate-600 text-xs px-3 py-1.5 rounded hover:bg-slate-50 flex items-center gap-1">
                  更多操作 <DownOutlined class="text-[10px]" />
                </button>
                <template #overlay>
                  <div class="bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[140px]">
                    <div @click="canDisable && bulkDisable(fetchData)" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2" :class="!canDisable ? 'opacity-50 cursor-not-allowed' : ''">
                      <StopOutlined class="text-sm" />批量禁用
                      <span v-if="selectedActiveCount > 0" class="text-xs text-slate-400 ml-auto">({{ selectedActiveCount }})</span>
                    </div>
                    <div @click="canActivate && bulkActivate(fetchData)" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2" :class="!canActivate ? 'opacity-50 cursor-not-allowed' : ''">
                      <CheckCircleOutlined class="text-sm" />批量激活
                      <span v-if="selectedInactiveCount > 0" class="text-xs text-slate-400 ml-auto">({{ selectedInactiveCount }})</span>
                    </div>
                    <div class="border-t border-slate-100 my-1"></div>
                    <div @click="selectedCount > 0 && bulkDelete(fetchData, fetchOrganizations)" class="px-4 py-2 text-sm text-red-500 hover:bg-red-50 cursor-pointer flex items-center gap-2">
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
              <button v-if="activeCategory !== 'all'" class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="导入"><ImportOutlined class="text-sm" /></button>
              <button class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="导出"><ExportOutlined class="text-sm" /></button>
              <button @click="handleSearch" class="p-1.5 text-slate-500 hover:text-primary hover:bg-slate-100 rounded" title="刷新"><ReloadOutlined class="text-sm" /></button>
            </div>
          </div>
        </div>

        <!-- Table -->
        <div class="bg-white rounded-xl shadow-sm overflow-hidden relative">
          <div class="overflow-x-auto" :key="columnConfigVersion">
            <table class="data-table min-w-[800px]">
              <thead>
                <tr>
                  <th class="w-10"><input type="checkbox" class="rounded border-gray-300 w-3.5 h-3.5" @change="selectAllChanged($event)" :checked="allSelected" /></th>
                  <th>名称</th>
                  <th>地址</th>
                  <th v-show="visibleColumnKeys['asset_code']">资产编号</th>
                  <th v-show="visibleColumnKeys['category']">资产类型</th>
                  <th v-show="visibleColumnKeys['platform']">{{ activeCategory === 'network' ? '厂商/型号' : '平台' }}</th>
                  <th v-show="visibleColumnKeys['device_type'] && activeCategory === 'network'">设备类型</th>
                  <th v-show="visibleColumnKeys['model'] && (activeCategory === 'host' || activeCategory === 'all')">型号</th>
                  <th v-show="visibleColumnKeys['serial_number'] && (activeCategory === 'host' || activeCategory === 'network' || activeCategory === 'all')">序列号</th>
                  <th v-show="visibleColumnKeys['cpu'] && (activeCategory === 'host' || activeCategory === 'all')">CPU</th>
                  <th v-show="visibleColumnKeys['memory'] && (activeCategory === 'host' || activeCategory === 'all')">内存</th>
                  <th v-show="visibleColumnKeys['system_disk'] && (activeCategory === 'host' || activeCategory === 'all')">系统盘</th>
                  <th v-show="visibleColumnKeys['data_disk'] && (activeCategory === 'host' || activeCategory === 'all')">数据盘</th>
                  <th v-show="visibleColumnKeys['db_type'] && (activeCategory === 'database' || activeCategory === 'all')">数据库类型</th>
                  <th v-show="visibleColumnKeys['version'] && (activeCategory === 'database' || activeCategory === 'all')">版本</th>
                  <th v-show="visibleColumnKeys['namespace'] && (activeCategory === 'database' || activeCategory === 'all')">命名空间</th>
                  <th v-show="visibleColumnKeys['organization']">节点</th>
                  <th v-show="visibleColumnKeys['is_active']">状态</th>
                  <th v-show="visibleColumnKeys['applicant'] && (activeCategory === 'host' || activeCategory === 'database' || activeCategory === 'all')">申请人</th>
                  <th v-show="visibleColumnKeys['credentials']">用户名密码</th>
                  <th v-show="visibleColumnKeys['notes']">描述</th>
                  <th class="text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="assets.length === 0 && !loading"><td :colspan="allColumnsConfig.filter(c => visibleColumnKeys[c.key]).length + 1" class="text-center py-16 text-slate-400">暂无数据</td></tr>
                <template v-else>
                  <tr v-for="asset in assets" :key="asset.id" :class="{ 'opacity-50 bg-slate-50': !asset.is_active }">
                    <td><input type="checkbox" class="rounded border-gray-300 w-3.5 h-3.5" v-model="asset.selected" @change="selectionChanged" /></td>
                    <td>
                      <p class="font-medium text-slate-900">{{ asset.name }}</p>
                    </td>
                    <td>
                      <template v-if="asset.url">
                        <span class="text-sm text-slate-600 font-mono">{{ asset.url }}</span>
                      </template>
                      <template v-else>
                        <div v-if="asset.external_address" class="text-sm text-slate-600 font-mono">
                          <span class="text-[10px] text-blue-500 font-medium mr-1">外</span>
                          <span>{{ asset.external_address }}</span>
                        </div>
                        <div v-if="asset.internal_address" class="text-sm text-slate-600 font-mono">
                          <span class="text-[10px] text-green-500 font-medium mr-1">内</span>
                          <span>{{ asset.internal_address }}</span>
                        </div>
                        <span v-if="!asset.external_address && !asset.internal_address && asset.address" class="text-sm text-slate-600 font-mono">{{ asset.address }}</span>
                        <span v-if="!asset.external_address && !asset.internal_address && !asset.address" class="text-sm text-slate-400">-</span>
                      </template>
                    </td>
                    <td v-show="visibleColumnKeys['asset_code']"><span class="text-sm text-slate-600 font-mono">{{ asset.asset_code || '' }}</span></td>
                    <td v-show="visibleColumnKeys['category']"><span class="text-sm text-slate-600">{{ categoryOptions.find(c => c.key === asset.category)?.label || asset.category }}</span></td>
                    <td v-show="visibleColumnKeys['platform']"><span class="text-sm text-slate-600">{{ activeCategory === 'network' ? (asset.platform && asset.model ? `${asset.platform}/${asset.model}` : (asset.platform || asset.model || '-')) : (asset.platform || asset.device_type || '-') }}</span></td>
                    <td v-show="visibleColumnKeys['device_type'] && activeCategory === 'network'"><span class="text-sm text-slate-600">{{ asset.device_type || '-' }}</span></td>
                    <td v-show="visibleColumnKeys['model'] && (activeCategory === 'host' || activeCategory === 'all')"><span class="text-sm text-slate-600">{{ asset.model || '' }}</span></td>
                    <td v-show="visibleColumnKeys['serial_number'] && (activeCategory === 'host' || activeCategory === 'network' || activeCategory === 'all')"><span class="text-sm text-slate-600 font-mono">{{ asset.serial_number || '' }}</span></td>
                    <td v-show="visibleColumnKeys['cpu'] && (activeCategory === 'host' || activeCategory === 'all')"><span class="text-sm text-slate-600">{{ asset.cpu || '' }}</span></td>
                    <td v-show="visibleColumnKeys['memory'] && (activeCategory === 'host' || activeCategory === 'all')"><span class="text-sm text-slate-600">{{ asset.memory || '' }}</span></td>
                    <td v-show="visibleColumnKeys['system_disk'] && (activeCategory === 'host' || activeCategory === 'all')"><span class="text-sm text-slate-600">{{ asset.system_disk || '' }}</span></td>
                    <td v-show="visibleColumnKeys['data_disk'] && (activeCategory === 'host' || activeCategory === 'all')"><span class="text-sm text-slate-600">{{ asset.data_disk || '' }}</span></td>
                    <td v-show="visibleColumnKeys['db_type'] && (activeCategory === 'database' || activeCategory === 'all')"><span class="text-sm text-slate-600">{{ asset.extra_data?.db_type || '' }}</span></td>
                    <td v-show="visibleColumnKeys['version'] && (activeCategory === 'database' || activeCategory === 'all')"><span class="text-sm text-slate-600">{{ asset.extra_data?.version || '' }}</span></td>
                    <td v-show="visibleColumnKeys['namespace'] && (activeCategory === 'database' || activeCategory === 'all')"><span class="text-sm text-slate-600">{{ asset.extra_data?.namespace || '' }}</span></td>
                    <td v-show="visibleColumnKeys['organization']"><span class="text-sm text-slate-600">{{ asset.organization_name || 'Default' }}</span></td>
                    <td v-show="visibleColumnKeys['is_active']">
                      <span v-if="asset.is_active" class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">启用</span>
                      <span v-else class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">禁用</span>
                    </td>
                    <td v-show="visibleColumnKeys['applicant'] && (activeCategory === 'host' || activeCategory === 'database' || activeCategory === 'all')" class="text-sm text-slate-600">{{ asset.extra_data?.applicant || '' }}</td>
                    <td v-show="visibleColumnKeys['credentials']" class="w-[220px] max-w-[220px]">
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
                    </td>
                    <td v-show="visibleColumnKeys['notes']" class="whitespace-normal max-w-[200px]"><span class="text-sm text-slate-600">{{ asset.notes || '' }}</span></td>
                    <td class="text-right">
                      <button v-if="asset.is_active" @click="openEditModal(asset)" class="bg-primary text-white px-2 py-0.5 rounded text-xs">更新</button>
                      <button v-else disabled class="bg-slate-200 text-slate-400 px-2 py-0.5 rounded cursor-not-allowed text-xs">更新</button>
                      <button v-if="asset.is_active" @click="handleDelete(asset, fetchData, fetchOrganizations)" class="border border-red-400 text-red-500 px-2 py-0.5 rounded text-xs ml-1">删除</button>
                      <button v-else disabled class="border border-slate-200 text-slate-300 px-2 py-0.5 rounded cursor-not-allowed text-xs ml-1">删除</button>
                    </td>
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

    <!-- Create/Edit Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showModal = false"></div>
      <div class="relative bg-white w-full max-w-2xl rounded-xl shadow-2xl max-h-[90vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-lg font-bold text-slate-900">{{ modalTitle }}</h2>
          <button @click="showModal = false" class="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
            <CloseOutlined class="text-slate-400" />
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleSubmit" class="space-y-5">
            <!-- Row 1: 资产名称、资产编号 -->
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">资产名称 <span class="text-red-500">*</span></label>
                <input v-model="form.name" type="text" class="input-field" placeholder="请输入资产名称" />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">资产编号</label>
                <input v-model="form.asset_code" type="text" class="input-field" placeholder="CI编号" />
              </div>
            </div>

            <!-- Row 2: 节点路径 -->
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1.5">节点</label>
              <select v-model="formSelectedOrgId" class="input-field">
                <option v-for="org in allOrgsForSelect" :key="org.id ?? 'default'" :value="org.id">
                  {{ org.path }}
                </option>
              </select>
            </div>

            <!-- Network设备专用布局 -->
            <template v-if="form.category === 'network'">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">资产类型 <span class="text-red-500">*</span></label>
                  <select v-model="form.category" class="input-field">
                    <option v-for="cat in categoryOptions" :key="cat.key" :value="cat.key">{{ cat.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">设备类型</label>
                  <select v-model="form.device_type" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="t in deviceTypeOptions" :key="t" :value="t">{{ t }}</option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">厂商</label>
                  <select v-model="form.platform" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="p in platformOptions[form.category]" :key="p" :value="p">{{ p }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">型号</label>
                  <input v-model="form.model" type="text" class="input-field" placeholder="如: C9300-48P" />
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">序列号</label>
                <input v-model="form.serial_number" type="text" class="input-field" placeholder="设备序列号" />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">地址</label>
                <input v-model="form.address" type="text" class="input-field" placeholder="支持格式: IP、IP:端口" />
              </div>
            </template>

            <!-- 其他类别布局 -->
            <template v-else>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">资产类型 <span class="text-red-500">*</span></label>
                  <select v-model="form.category" class="input-field">
                    <option v-for="cat in categoryOptions" :key="cat.key" :value="cat.key">{{ cat.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">平台</label>
                  <select v-model="form.platform" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="p in platformOptions[form.category]" :key="p" :value="p">{{ p }}</option>
                  </select>
                </div>
              </div>
              <div v-if="form.category === 'database'" class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">数据库类型</label>
                  <select v-model="form.db_type" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="t in dbTypeOptions" :key="t" :value="t">{{ t }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">版本</label>
                  <input v-model="form.version" type="text" class="input-field" placeholder="数据库版本" />
                </div>
              </div>
              <div v-if="form.category === 'database'">
                <label class="block text-xs font-medium text-slate-600 mb-1.5">命名空间</label>
                <input v-model="form.namespace" type="text" class="input-field" placeholder="命名空间" />
              </div>
              <div v-if="['host', 'database'].includes(form.category)" class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">外网地址</label>
                  <input v-model="form.external_address" type="text" class="input-field" placeholder="外网IP地址" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">内网地址</label>
                  <input v-model="form.internal_address" type="text" class="input-field" placeholder="内网IP地址" />
                </div>
              </div>
              <div v-else-if="['cloud', 'web', 'gpt'].includes(form.category)">
                <label class="block text-xs font-medium text-slate-600 mb-1.5">URL</label>
                <input v-model="form.url" type="text" class="input-field" placeholder="https://" />
              </div>
            </template>

            <!-- 用户名密码区域 -->
            <div class="border border-slate-200 rounded-lg overflow-hidden">
              <div class="bg-slate-50 px-4 py-2.5 border-b border-slate-200">
                <label class="text-xs font-medium text-slate-600">用户名密码</label>
              </div>
              <div class="p-4">
                <!-- 已有凭证列表 -->
                <div v-if="formCredentials.length > 0" class="space-y-2 mb-4">
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
                          class="input-field text-sm flex-1"
                          @blur="stopFieldEdit"
                          @keyup.enter="stopFieldEdit"
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
                          class="input-field text-sm flex-1"
                          @blur="stopFieldEdit"
                          @keyup.enter="stopFieldEdit"
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
                <!-- 添加新凭证表单 -->
                <div class="flex items-end gap-3">
                  <div class="flex-1">
                    <label class="block text-xs text-slate-500 mb-1">用户名</label>
                    <input v-model="newCredentialForm.username" type="text" class="input-field text-sm" placeholder="输入用户名" />
                  </div>
                  <div class="flex-1 relative">
                    <label class="block text-xs text-slate-500 mb-1">密码</label>
                    <input v-model="newCredentialForm.password" :type="showPassword ? 'text' : 'password'" class="input-field text-sm w-full pr-8" placeholder="输入密码" />
                    <button type="button" @click="showPassword = !showPassword" class="absolute right-2 top-[calc(50%+10px)] -translate-y-1/2 text-slate-400 hover:text-slate-600">
                      <EyeOutlined v-if="!showPassword" class="text-sm" />
                      <EyeInvisibleOutlined v-else class="text-sm" />
                    </button>
                  </div>
                  <button type="button" @click="addCredentialToForm" class="bg-primary text-white px-4 py-2 rounded text-sm hover:bg-blue-600 transition-colors h-[38px]">
                    <PlusCircleOutlined class="mr-1" /> 添加
                  </button>
                </div>
              </div>
            </div>

            <!-- 数据库专属字段 -->
            <template v-if="form.category === 'database'">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">申请人</label>
                <input v-model="form.applicant" type="text" class="input-field" placeholder="申请人姓名" />
              </div>
            </template>

            <!-- 主机专属字段 -->
            <template v-if="form.category === 'host'">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">型号</label>
                  <input v-model="form.model" type="text" class="input-field" placeholder="设备型号" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">序列号</label>
                  <input v-model="form.serial_number" type="text" class="input-field" placeholder="序列号" />
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">CPU</label>
                  <input v-model="form.cpu" type="text" class="input-field" placeholder="如: 8核" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">内存</label>
                  <input v-model="form.memory" type="text" class="input-field" placeholder="如: 16GB" />
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">系统盘</label>
                  <input v-model="form.system_disk" type="text" class="input-field" placeholder="如: 500GB SSD" />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">数据盘</label>
                  <input v-model="form.data_disk" type="text" class="input-field" placeholder="如: 2TB HDD" />
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">申请人</label>
                <input v-model="form.applicant" type="text" class="input-field" placeholder="申请人姓名" />
              </div>
            </template>

            <!-- 描述 -->
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1.5">描述</label>
              <textarea v-model="form.notes" class="input-field h-20 resize-none" placeholder="资产描述或备注"></textarea>
            </div>

            <!-- 操作按钮 -->
            <div class="flex justify-end gap-3 pt-2 border-t border-slate-100">
              <button type="button" @click="showModal = false" class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors">
                取消
              </button>
              <button type="submit" :disabled="modalLoading" class="btn-primary">
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
          <form @submit.prevent="handleOrgModalSubmit" class="space-y-4">
            <div><label class="block text-xs font-medium text-slate-600 mb-1.5">节点名称 <span class="text-red-500">*</span></label><input v-model="orgForm.name" type="text" class="input-field" placeholder="请输入节点名称" autofocus /></div>
            <div class="flex justify-end gap-3 pt-2 border-t border-slate-100">
              <button type="button" @click="showOrgModal = false" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">取消</button>
              <button type="submit" :disabled="orgModalLoading" class="btn-primary">{{ orgModalLoading ? '处理中...' : '确定' }}</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>