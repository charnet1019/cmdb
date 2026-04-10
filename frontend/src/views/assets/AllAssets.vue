<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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
  FolderAddOutlined
} from '@ant-design/icons-vue'
import { useAssets } from './composables/useAssets'
import { useOrganizations } from './composables/useOrganizations'
import { useCredentials } from './composables/useCredentials'
import { useTypeTree, categories, platformOptions, categoryOptions } from './composables/useTypeTree'
import type { Asset, AssetCategory } from '@/types'

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
  flattenedOrgs,
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
  selectOrganization,
  getOrgPath,
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
  formCredentials,
  copyUsername,
  copyPassword,
  viewPassword,
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

// Tree view mode
const treeViewMode = ref<'asset' | 'type'>('asset')

// Search
const searchQuery = ref('')

// Modal
const showModal = ref(false)
const modalLoading = ref(false)
const editingAsset = ref<Asset | null>(null)

// Form
const form = ref({
  name: '',
  asset_code: '',
  category: 'host' as AssetCategory,
  address: '',
  platform: '',
  device_type: '',
  model: '',
  serial_number: '',
  url: '',
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
  } else {
    selectedTypeNodeId.value = 'all'
    activeCategory.value = 'all'
    selectedOrgId.value = null
  }
  fetchData()
}

// Change category tab
function changeCategory(category: AssetCategory | 'all') {
  activeCategory.value = category
  selectedTypeNodeId.value = category === 'all' ? 'all' : category
  if (category === 'all') {
    treeViewMode.value = 'asset'
  } else {
    treeViewMode.value = 'type'
  }
  page.value = 1
  fetchData()
}

// Handle root click - select root and refresh assets
function handleRootClick() {
  selectedOrgId.value = null
  page.value = 1
  fetchData()
  toggleRootExpansion()
}

// Handle org click - always select and refresh, plus toggle if has children
function handleOrgClick(org: { id: number; name: string; hasChildren: boolean }) {
  selectOrganization(org.id, () => {
    page.value = 1
    fetchData()
  })
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
    platform: '',
    device_type: '',
    model: '',
    serial_number: '',
    url: '',
    notes: ''
  }

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
    platform: asset.platform || '',
    device_type: asset.device_type || '',
    model: asset.model || '',
    serial_number: asset.serial_number || '',
    url: asset.url || '',
    notes: asset.notes || ''
  }
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
    const data = {
      name: form.value.name,
      asset_code: form.value.asset_code || undefined,
      category: form.value.category,
      address: form.value.address || undefined,
      platform: form.value.platform || undefined,
      device_type: form.value.device_type || undefined,
      model: form.value.model || undefined,
      serial_number: form.value.serial_number || undefined,
      url: form.value.url || undefined,
      notes: form.value.notes || undefined,
      organization_id: selectedOrgId.value || undefined
    }

    if (editingAsset.value) {
      await fetch(`/api/v1/assets/${editingAsset.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      }).then(r => r.json())
      message.success('资产更新成功')
    } else {
      const newAsset = await fetch('/api/v1/assets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      }).then(r => r.json())

      // Create credentials
      for (const cred of formCredentials.value) {
        if (cred.username && cred.password && newAsset.id) {
          await fetch(`/api/v1/assets/${newAsset.id}/credentials`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: cred.username, password: cred.password, credential_type: 'password' })
          })
        }
      }
      message.success('资产创建成功')
    }

    showModal.value = false
    fetchData()
    fetchAssetStats()
    fetchOrganizations()
  } catch (error: any) {
    message.error(error.response?.data?.detail || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

onMounted(() => { fetchData(); fetchOrganizations(); fetchAssetStats() })
</script>

<template>
  <div class="space-y-4">
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
                    <div @click="selectedCount > 0 && bulkDelete(fetchData)" class="px-4 py-2 text-sm text-red-500 hover:bg-red-50 cursor-pointer flex items-center gap-2">
                      <DeleteOutlined class="text-sm" />批量删除
                      <span v-if="selectedCount > 0" class="text-xs text-slate-400 ml-auto">({{ selectedCount }})</span>
                    </div>
                  </div>
                </template>
              </Dropdown>
            </div>
            <input v-model="searchQuery" type="text" placeholder="搜索" class="border border-gray-200 rounded py-1.5 px-3 text-xs w-72" @keyup.enter="handleSearch" />
          </div>
        </div>

        <!-- Table -->
        <div class="bg-white rounded-xl shadow-sm overflow-hidden relative">
          <div class="overflow-x-auto">
            <table class="data-table min-w-[800px]">
              <thead>
                <tr>
                  <th class="w-10"><input type="checkbox" class="rounded border-gray-300 w-3.5 h-3.5" @change="selectAllChanged($event)" :checked="allSelected" /></th>
                  <th>名称</th>
                  <th>地址</th>
                  <th>类型/平台</th>
                  <th>用户名密码</th>
                  <th class="text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="assets.length === 0 && !loading"><td colspan="6" class="text-center py-16 text-slate-400">暂无数据</td></tr>
                <template v-else>
                  <tr v-for="asset in assets" :key="asset.id" :class="{ 'opacity-50 bg-slate-50': !asset.is_active }">
                    <td><input type="checkbox" class="rounded border-gray-300 w-3.5 h-3.5" v-model="asset.selected" @change="selectionChanged" /></td>
                    <td>
                      <p class="font-medium text-slate-900">{{ asset.name }}</p>
                      <p v-if="asset.asset_code" class="text-xs text-slate-400">{{ asset.asset_code }}</p>
                    </td>
                    <td><span class="text-sm text-slate-600 font-mono">{{ asset.url || asset.address || '-' }}</span></td>
                    <td><span class="text-sm text-slate-600">{{ asset.platform || asset.device_type || '-' }}</span></td>
                    <td>
                      <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                        <span class="font-medium">{{ cred.username }}</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <span v-if="decryptedPasswords.has(cred.id)" class="text-slate-700 font-mono ml-1">{{ decryptedPasswords.get(cred.id) }}</span>
                        <span v-else class="text-slate-400 font-mono ml-1">********</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyPassword(cred)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <template v-if="asset.is_active">
                          <EyeOutlined v-if="!decryptedPasswords.has(cred.id)" class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" />
                          <EyeInvisibleOutlined v-else class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" />
                        </template>
                        <EyeOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed ml-1" />
                      </div>
                    </td>
                    <td class="text-right">
                      <button v-if="asset.is_active" @click="openEditModal(asset)" class="bg-primary text-white px-2 py-0.5 rounded text-xs">更新</button>
                      <button v-else disabled class="bg-slate-200 text-slate-400 px-2 py-0.5 rounded cursor-not-allowed text-xs">更新</button>
                      <button v-if="asset.is_active" @click="handleDelete(asset, fetchData)" class="border border-red-400 text-red-500 px-2 py-0.5 rounded text-xs ml-1">删除</button>
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

    <!-- Create/Edit Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showModal = false"></div>
      <div class="relative bg-white w-full max-w-2xl rounded-xl shadow-2xl max-h-[90vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-lg font-bold text-slate-900">{{ modalTitle }}</h2>
          <button @click="showModal = false" class="p-1.5 hover:bg-slate-100 rounded-lg"><CloseOutlined class="text-slate-400" /></button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleSubmit" class="space-y-5">
            <div class="grid grid-cols-2 gap-4">
              <div><label class="block text-xs font-medium text-slate-600 mb-1.5">资产名称 <span class="text-red-500">*</span></label><input v-model="form.name" type="text" class="input-field" /></div>
              <div><label class="block text-xs font-medium text-slate-600 mb-1.5">资产编号</label><input v-model="form.asset_code" type="text" class="input-field" /></div>
            </div>
            <div><label class="block text-xs font-medium text-slate-600 mb-1.5">节点</label><div class="input-field bg-slate-50 text-slate-600 flex items-center gap-2"><FolderOutlined class="text-sm text-slate-400" /><span class="truncate">{{ getOrgPath(selectedOrgId) }}</span></div></div>
            <div class="grid grid-cols-2 gap-4">
              <div><label class="block text-xs font-medium text-slate-600 mb-1.5">资产类型</label><select v-model="form.category" class="input-field"><option v-for="cat in categoryOptions" :key="cat.key" :value="cat.key">{{ cat.label }}</option></select></div>
              <div><label class="block text-xs font-medium text-slate-600 mb-1.5">平台</label><select v-model="form.platform" class="input-field"><option value="">请选择</option><option v-for="p in platformOptions[form.category]" :key="p" :value="p">{{ p }}</option></select></div>
            </div>
            <div><label class="block text-xs font-medium text-slate-600 mb-1.5">地址</label><input v-model="form.address" type="text" class="input-field" placeholder="IP:端口" /></div>
            <div><label class="block text-xs font-medium text-slate-600 mb-1.5">描述</label><textarea v-model="form.notes" class="input-field h-20 resize-none"></textarea></div>
            <div class="flex justify-end gap-3 pt-2 border-t border-slate-100">
              <button type="button" @click="showModal = false" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">取消</button>
              <button type="submit" :disabled="modalLoading" class="btn-primary">{{ modalLoading ? '处理中...' : '保存' }}</button>
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