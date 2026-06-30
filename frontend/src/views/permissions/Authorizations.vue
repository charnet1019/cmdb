<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, EditOutlined, BlockOutlined, CheckCircleOutlined, DeleteOutlined, CloseOutlined } from '@ant-design/icons-vue'
import { formatDateTime } from '@/utils/datetime'
import {
  getAuthorizations,
  createAuthorization,
  updateAuthorization,
  deleteAuthorization,
  getUsersForAuth,
  getGroupsForAuth,
  getAssetsForAuth,
  getOrganizationsForAuth
} from '@/api/authorizations'
import type { AuthorizationCreate } from '@/api/authorizations'

const router = useRouter()
const route = useRoute()

// Data
const authorizations = ref<any[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const limit = ref(20)

// Filters
const entityTypeFilter = ref('')
const isActiveFilter = ref<boolean | null>(null)

// Modal
const showModal = ref(false)
const modalLoading = ref(false)
const isEditMode = ref(false)
const editingAuthId = ref<number | null>(null)

// Track whether selection options have been loaded
const selectionsLoaded = ref(false)
let fetchSelectionsPromise: Promise<void> | null = null

// Fetch selection options (deduplicated — concurrent callers share one request)
async function fetchSelectionOptions() {
  if (fetchSelectionsPromise) return fetchSelectionsPromise
  fetchSelectionsPromise = (async () => {
    try {
      const [usersData, groupsData, assetsData, orgsData] = await Promise.all([
        getUsersForAuth(),
        getGroupsForAuth(),
        getAssetsForAuth(),
        getOrganizationsForAuth()
      ])
      users.value = usersData
      groups.value = groupsData
      assets.value = assetsData
      organizations.value = orgsData
      buildTree()
      selectionsLoaded.value = true
    } catch {
      // Handle silently
    } finally {
      fetchSelectionsPromise = null
    }
  })()
  return fetchSelectionsPromise
}

// Form
const form = ref({
  entity_type: 'user' as 'user' | 'group',
  entity_id: null as number | null,
  target_type: 'asset' as 'asset' | 'organization',
  target_ids: [] as string[],
  permissions: [] as string[],
  valid_until: ''
})

// Selection options
const users = ref<Array<{ id: number; name: string; full_name: string | null }>>([])
const groups = ref<Array<{ id: number; name: string }>>([])
const assets = ref<Array<{ id: string; name: string; category: string; internal_address: string | null; external_address: string | null; organization_id: number | null }>>([])
const organizations = ref<Array<{ id: number | null; name: string; path: string | null; name_path: string }>>([])

// Asset picker modal
const showAssetPicker = ref(false)
const pickerSearch = ref('')
const pickerSelectedOrgId = ref<number | null>(null)
const pickerAssets = ref<Array<{ id: string; name: string; category: string; internal_address: string | null; external_address: string | null; organization_id: number | null }>>([])
const pickerSelectedAssetIds = ref<string[]>([])

// Org tree for picker (built from flat data)
interface OrgTreeNode {
  id: number | null
  title: string
  key: string
  children: OrgTreeNode[]
}
const orgTreeData = ref<OrgTreeNode[]>([])


// Permission options
const permissionOptions = [
  { key: 'view', label: '查看资产' },
  { key: 'manage', label: '管理资产' },
  { key: 'view_users', label: '查看用户' },
  { key: 'user_mgmt', label: '用户管理' },
  { key: 'sys_config', label: '系统设置' },
  { key: 'audit_log', label: '日志审计' },
  { key: 'view_pwd', label: '查看密码' }
]

// Format organization name path (e.g. "Default/开发部/数据库")
function formatOrgPath(org: { id: number | null; name: string; name_path: string }): string {
  if (org.id === null) return 'Default'
  return org.name_path || org.name
}

// Build org tree from flat list
function buildOrgTree(flatOrgs: Array<{ id: number | null; name: string; path: string | null; name_path: string }>): OrgTreeNode[] {
  const map = new Map<number, OrgTreeNode>()
  const roots: OrgTreeNode[] = []

  for (const org of flatOrgs) {
    if (org.id === null) {
      // Default root — will be added separately
      continue
    }
    map.set(org.id, { id: org.id, title: org.name, key: String(org.id), children: [] })
  }

  // Derive parent from path: "7/12/13" → parent id = 12
  for (const org of flatOrgs) {
    if (org.id === null) continue
    const node = map.get(org.id)!
    let parentId: number | null = null
    if (org.path && org.path.includes('/')) {
      const parts = org.path.split('/')
      parentId = parseInt(parts[parts.length - 2])
    }
    if (parentId === null || !map.has(parentId)) {
      roots.push(node)
    } else {
      map.get(parentId)!.children.push(node)
    }
  }

  return roots
}

// Build org tree on data load
function buildTree() {
  orgTreeData.value = buildOrgTree(organizations.value)
}

// Open asset picker — sync local selection from form
function openAssetPicker() {
  showAssetPicker.value = true
  pickerSearch.value = ''
  pickerSelectedOrgId.value = null
  pickerAssets.value = assets.value
  pickerSelectedAssetIds.value = [...form.value.target_ids]
}

// Org tree select callback
function onPickerTreeSelect(_selected: any, info: { node: OrgTreeNode & { id: number | null } }) {
  if (info.node.id === null || info.node.key === '__all__') {
    pickerSelectedOrgId.value = null
  } else {
    pickerSelectedOrgId.value = info.node.id
  }
  filterPickerAssets()
}

// Filter picker assets by selected org + search
function filterPickerAssets() {
  let filtered = assets.value
  if (pickerSelectedOrgId.value !== null) {
    filtered = filtered.filter(a => a.organization_id === pickerSelectedOrgId.value)
  }
  if (pickerSearch.value) {
    const search = pickerSearch.value.toLowerCase()
    filtered = filtered.filter(a =>
      a.name.toLowerCase().includes(search) ||
      a.category.toLowerCase().includes(search)
    )
  }
  pickerAssets.value = filtered
}

watch([pickerSearch], () => {
  filterPickerAssets()
})

// Toggle asset selection in picker
function togglePickerAsset(assetId: string) {
  const idx = pickerSelectedAssetIds.value.indexOf(assetId)
  if (idx === -1) {
    pickerSelectedAssetIds.value.push(assetId)
  } else {
    pickerSelectedAssetIds.value.splice(idx, 1)
  }
}

// Confirm picker — apply selections to form and close
function confirmPickerSelection() {
  form.value.target_ids = [...pickerSelectedAssetIds.value]
  showAssetPicker.value = false
}

// Cancel picker — discard changes
function cancelPickerSelection() {
  showAssetPicker.value = false
}

// Get asset label by ID
function getAssetLabel(id: string): string {
  const asset = assets.value.find((a: { id: string; name: string; category: string }) => a.id === id)
  return asset ? `${asset.name} (${asset.category})` : id
}

// Remove a target ID
function removeTargetId(id: string) {
  const idx = form.value.target_ids.indexOf(id)
  if (idx !== -1) form.value.target_ids.splice(idx, 1)
}

// Get target name for edit mode display
function getTargetName(): string {
  if (form.value.target_type === 'asset') {
    return form.value.target_ids
      .map(id => {
        const asset = assets.value.find((a: { id: string; name: string }) => a.id === id)
        return asset ? asset.name : id
      })
      .join(', ')
  }
  return form.value.target_ids
    .map(id => {
      if (id === '__all__') return 'Default'
      const org = organizations.value.find((o: { id: number | null; name_path: string }) => String(o.id ?? '__all__') === id)
      return org ? org.name_path : id
    })
    .join(', ')
}

// Fetch authorizations
async function fetchAuthorizations() {
  loading.value = true
  try {
    const result = await getAuthorizations({
      page: page.value,
      limit: limit.value,
      entity_type: entityTypeFilter.value || undefined,
      is_active: isActiveFilter.value ?? undefined
    })
    authorizations.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    message.error('获取授权列表失败')
    authorizations.value = []
  } finally {
    loading.value = false
  }
}

// Handle search
function handleSearch() {
  page.value = 1
  fetchAuthorizations()
}

// Handle page change
function handlePageChange(newPage: number) {
  page.value = newPage
  fetchAuthorizations()
}

// Open create modal
function openCreateModal() {
  isEditMode.value = false
  editingAuthId.value = null
  form.value = {
    entity_type: 'user',
    entity_id: null,
    target_type: 'asset',
    target_ids: [] as string[],
    permissions: [],
    valid_until: ''
  }
  showModal.value = true
}

// Open edit modal
async function openEditModal(auth: any) {
  isEditMode.value = true
  editingAuthId.value = auth.id
  form.value = {
    entity_type: auth.entity_type,
    entity_id: auth.entity_id,
    target_type: auth.target_type,
    target_ids: auth.target_ids || [],
    permissions: auth.permissions || [],
    valid_until: auth.valid_until ? auth.valid_until.slice(0, 16) : ''
  }
  // Wait for selection data before showing modal, so a-select has options
  if (!selectionsLoaded.value) {
    await fetchSelectionOptions()
  }
  showModal.value = true
}

// Submit form
async function handleSubmit() {
  if (!isEditMode.value) {
    if (!form.value.entity_id) {
      message.error('请选择授权对象')
      return
    }
    if (!form.value.target_ids.length) {
      message.error('请选择资产')
      return
    }
  } else {
    if (!form.value.target_ids.length) {
      message.error('请至少保留一个资产')
      return
    }
  }
  if (form.value.permissions.length === 0) {
    message.error('请选择权限')
    return
  }

  modalLoading.value = true
  try {
    if (isEditMode.value && editingAuthId.value) {
      // Update existing authorization
      const updateData: any = {
        permissions: form.value.permissions,
      }
      if (form.value.valid_until) {
        updateData.valid_until = form.value.valid_until
      }
      if (form.value.target_ids.length > 0) {
        updateData.target_ids = form.value.target_ids
      }
      await updateAuthorization(editingAuthId.value, updateData)
      message.success('授权更新成功')
    } else {
      // Create new authorization
      const data: AuthorizationCreate = {
        entity_type: form.value.entity_type,
        entity_id: form.value.entity_id!,
        target_type: form.value.target_type,
        target_ids: form.value.target_ids,
        permissions: form.value.permissions,
      }
      if (form.value.valid_until) {
        data.valid_until = form.value.valid_until
      }
      await createAuthorization(data)
      message.success('授权创建成功')
    }
    showModal.value = false
    fetchAuthorizations()
  } catch (error: any) {
    message.error(error.response?.data?.detail || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

// Delete authorization
async function handleDelete(auth: any) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除对 "${auth.entity_name}" 的授权吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    centered: true,
    async onOk() {
      try {
        await deleteAuthorization(auth.id)
        message.success('授权已删除')
        fetchAuthorizations()
      } catch {
        message.error('删除失败')
      }
    }
  })
}

// Toggle authorization status
async function toggleStatus(auth: any) {
  try {
    await updateAuthorization(auth.id, { is_active: !auth.is_active })
    message.success(auth.is_active ? '授权已禁用' : '授权已启用')
    fetchAuthorizations()
  } catch {
    message.error('操作失败')
  }
}

// Get permission label
function getPermissionLabel(key: string): string {
  const opt = permissionOptions.find(p => p.key === key)
  return opt ? opt.label : key
}

// Initial load
onMounted(() => {
  // Restore state from URL
  const query = route.query
  if (query.page) page.value = Number(query.page)
  if (query.entity) entityTypeFilter.value = query.entity as string
  if (query.active === 'true') isActiveFilter.value = true
  else if (query.active === 'false') isActiveFilter.value = false

  fetchAuthorizations()
  fetchSelectionOptions()
})

// Watch entity_type — reset entity_id when switching
watch(() => form.value.entity_type, () => {
  form.value.entity_id = null
})

// Watch target_type — reset target_ids when switching
watch(() => form.value.target_type, () => {
  form.value.target_ids = []
})

// Sync state to URL
watch([page, entityTypeFilter, isActiveFilter], () => {
  const query: Record<string, string> = {}
  if (page.value !== 1) query.page = String(page.value)
  if (entityTypeFilter.value) query.entity = entityTypeFilter.value
  if (isActiveFilter.value !== null) query.active = String(isActiveFilter.value)
  router.replace({ query })
}, { deep: true })
</script>

<template>
  <div class="space-y-4">
    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-4 flex-wrap">
        <button @click="openCreateModal" class="btn-primary flex items-center gap-2">
          <PlusOutlined />
          新增授权
        </button>
        <select v-model="entityTypeFilter" @change="handleSearch" class="input-field w-32">
          <option value="">全部对象</option>
          <option value="user">用户</option>
          <option value="group">用户组</option>
        </select>
        <select v-model="isActiveFilter" @change="handleSearch" class="input-field w-32">
          <option :value="null">全部状态</option>
          <option :value="true">Active</option>
          <option :value="false">Disabled</option>
        </select>
        <button @click="handleSearch" class="btn-secondary">筛选</button>
      </div>
    </div>

    <!-- Authorizations Table -->
    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <table class="data-table">
        <thead>
          <tr>
            <th>用户/用户组</th>
            <th>资产</th>
            <th>权限类型</th>
            <th>授权时间</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6" class="text-center py-8 text-slate-500">加载中...</td>
          </tr>
          <tr v-else-if="authorizations.length === 0">
            <td colspan="6" class="text-center py-8 text-slate-500">暂无数据</td>
          </tr>
          <tr v-for="auth in authorizations" :key="auth.id">
            <td>
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-full flex items-center justify-center" :class="auth.entity_type === 'user' ? 'bg-blue-100' : 'bg-purple-100'">
                  <span class="font-medium text-sm" :class="auth.entity_type === 'user' ? 'text-blue-700' : 'text-purple-700'">
                    {{ auth.entity_name?.[0]?.toUpperCase() || 'G' }}
                  </span>
                </div>
                <div>
                  <p class="font-medium text-slate-900">{{ auth.entity_name }}</p>
                  <p class="text-xs text-slate-500">
                    {{ auth.entity_type === 'user' ? '用户' : '用户组' }}
                  </p>
                </div>
              </div>
            </td>
            <td>
              <div>
                <p class="font-medium text-slate-900">{{ auth.target_name }}</p>
                <p class="text-xs text-slate-500">{{ auth.target_type === 'asset' ? '资产' : '资产组' }}</p>
              </div>
            </td>
            <td>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="perm in auth.permissions"
                  :key="perm"
                  class="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded font-bold"
                >
                  {{ getPermissionLabel(perm) }}
                </span>
              </div>
            </td>
            <td>
              <span class="text-sm text-slate-600">{{ formatDateTime(auth.created_at) }}</span>
              <p v-if="auth.valid_until" class="text-xs text-slate-500">有效期至: {{ formatDateTime(auth.valid_until) }}</p>
            </td>
            <td>
              <span class="badge" :class="auth.is_active ? 'badge-success' : 'bg-slate-100 text-slate-500'">
                <span class="inline-block w-1.5 h-1.5 rounded-full mr-1" :class="auth.is_active ? 'bg-success' : 'bg-slate-400'"></span>
                {{ auth.is_active ? 'Active' : 'Disabled' }}
              </span>
            </td>
            <td>
              <div class="flex items-center gap-1">
                <button @click="openEditModal(auth)" class="p-1.5 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600" title="编辑">
                  <EditOutlined :style="{ fontSize: '16px' }" />
                </button>
                <button @click="toggleStatus(auth)" class="p-1.5 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600" :title="auth.is_active ? '禁用' : '启用'">
                  <component :is="auth.is_active ? BlockOutlined : CheckCircleOutlined" :style="{ fontSize: '16px' }" />
                </button>
                <button @click="handleDelete(auth)" class="p-1.5 hover:bg-red-50 rounded text-slate-400 hover:text-red-600" title="删除">
                  <DeleteOutlined :style="{ fontSize: '16px' }" />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div class="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
        <span class="text-sm text-slate-500">共 {{ total }} 条记录</span>
        <div class="flex items-center gap-2">
          <button
            @click="handlePageChange(page - 1)"
            :disabled="page === 1"
            class="px-3 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50"
          >
            上一页
          </button>
          <span class="text-sm text-slate-600">{{ page }} / {{ Math.ceil(total / limit) || 1 }}</span>
          <button
            @click="handlePageChange(page + 1)"
            :disabled="page >= Math.ceil(total / limit)"
            class="px-3 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50"
          >
            下一页
          </button>
        </div>
      </div>
    </div>

    <!-- Create/Edit Authorization Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showModal = false"></div>
      <div class="relative bg-white w-full max-w-2xl rounded-xl shadow-2xl max-h-[90vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">{{ isEditMode ? '编辑授权' : '新增授权' }}</h2>
          <button @click="showModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleSubmit" class="space-y-6">
            <!-- Entity Selection (disabled in edit mode) -->
            <div v-if="!isEditMode">
              <label class="block text-sm font-medium text-slate-700 mb-2">授权对象</label>
              <div class="flex gap-4 mb-3">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="radio" v-model="form.entity_type" value="user" class="text-primary" />
                  <span class="text-sm">用户</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="radio" v-model="form.entity_type" value="group" class="text-primary" />
                  <span class="text-sm">用户组</span>
                </label>
              </div>
              <a-select
                v-if="form.entity_type === 'user'"
                v-model:value="form.entity_id"
                :placeholder="form.entity_type === 'user' ? '请选择用户' : '请选择用户组'"
                :options="users.map(u => ({ label: u.full_name ? `${u.name} (${u.full_name})` : u.name, value: u.id }))"
                show-search
                :allow-clear="true"
                :filter-option="(input: string, option: any) => (option.label || '').toLowerCase().includes(input.toLowerCase())"
                style="width: 100%"
              />
              <a-select
                v-else
                v-model:value="form.entity_id"
                :placeholder="form.entity_type === 'user' ? '请选择用户' : '请选择用户组'"
                :options="groups.map(g => ({ label: g.name, value: g.id }))"
                show-search
                :allow-clear="true"
                :filter-option="(input: string, option: any) => (option.label || '').toLowerCase().includes(input.toLowerCase())"
                style="width: 100%"
              />
            </div>

            <!-- Show entity info in edit mode -->
            <div v-else>
              <label class="block text-sm font-medium text-slate-700 mb-2">授权对象</label>
              <div class="p-3 bg-slate-50 rounded-lg">
                <p class="font-medium text-slate-900">
                  {{ form.entity_type === 'user'
                    ? users.find(u => u.id === form.entity_id)?.name
                    : groups.find(g => g.id === form.entity_id)?.name }}
                </p>
                <p class="text-sm text-slate-500">
                  {{ form.entity_type === 'user' ? '用户' : '用户组' }}
                </p>
              </div>
            </div>

            <!-- Target Selection -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-2">资产范围</label>
              <div v-if="!isEditMode" class="flex gap-4 mb-3">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="radio" v-model="form.target_type" value="asset" class="text-primary" />
                  <span class="text-sm">单个资产</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="radio" v-model="form.target_type" value="organization" class="text-primary" />
                  <span class="text-sm">节点</span>
                </label>
              </div>
              <div v-if="form.target_type === 'asset'" class="space-y-2">
                <!-- Edit mode: clickable tags for current assets + picker -->
                <div v-if="isEditMode" class="space-y-2">
                  <div
                    @click="openAssetPicker"
                    class="flex items-center flex-wrap gap-1 min-h-[36px] px-2 border border-slate-300 rounded-lg cursor-text hover:border-primary transition-colors"
                  >
                    <template v-for="id in form.target_ids" :key="id">
                      <span class="inline-flex items-center gap-1 px-2 py-0.5 bg-primary/10 text-primary text-sm rounded">
                        {{ getAssetLabel(id) }}
                        <span @click.stop="removeTargetId(id)" class="cursor-pointer hover:text-primary-dark" style="font-size: 12px">×</span>
                      </span>
                    </template>
                    <span class="text-sm text-slate-400 ml-1">点击添加资产</span>
                  </div>
                </div>
                <!-- Create mode: custom tag input — click to open picker -->
                <div
                  v-else
                  @click="openAssetPicker"
                  class="flex items-center flex-wrap gap-1 min-h-[36px] px-2 border border-slate-300 rounded-lg cursor-text hover:border-primary transition-colors"
                >
                  <template v-for="id in form.target_ids" :key="id">
                    <span class="inline-flex items-center gap-1 px-2 py-0.5 bg-primary/10 text-primary text-sm rounded">
                      {{ getAssetLabel(id) }}
                      <span @click.stop="removeTargetId(id)" class="cursor-pointer hover:text-primary-dark" style="font-size: 12px">×</span>
                    </span>
                  </template>
                  <span v-if="form.target_ids.length === 0" class="text-sm text-slate-400 ml-1">请选择资产</span>
                </div>
              </div>
              <!-- Organization target -->
              <div v-else>
                <a-select
                  v-model:value="form.target_ids"
                  mode="multiple"
                  :placeholder="'请选择节点'"
                  :options="organizations.map(o => ({ label: formatOrgPath(o), value: o.id === null ? '__all__' : String(o.id) }))"
                  show-search
                  :allow-clear="true"
                  :filter-option="(input: string, option: any) => (option.label || '').toLowerCase().includes(input.toLowerCase())"
                  style="width: 100%"
                />
              </div>
            </div>

            <!-- Permissions -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-2">权限类型</label>
              <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
                <label
                  v-for="opt in permissionOptions"
                  :key="opt.key"
                  class="flex items-center gap-2 cursor-pointer p-2 border rounded-lg hover:bg-slate-50"
                  :class="form.permissions.includes(opt.key) ? 'border-primary bg-primary/5' : ''"
                >
                  <input
                    type="checkbox"
                    :value="opt.key"
                    v-model="form.permissions"
                    class="text-primary"
                  />
                  <span class="text-sm text-slate-600">{{ opt.label }}</span>
                </label>
              </div>
            </div>

            <!-- Validity -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-2">有效期至 (可选)</label>
              <a-date-picker
                v-model:value="form.valid_until"
                show-time
                format="YYYY-MM-DD HH:mm"
                value-format="YYYY-MM-DDTHH:mm"
                placeholder="选择到期时间"
                style="width: 100%;"
              />
            </div>

            <!-- Actions -->
            <div class="flex justify-end gap-2 pt-4">
              <button type="button" @click="showModal = false" class="btn-secondary">取消</button>
              <button type="submit" :disabled="modalLoading" class="btn-primary">
                {{ modalLoading ? '处理中...' : (isEditMode ? '保存修改' : '创建授权') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Asset Picker Modal -->
    <div v-if="showAssetPicker" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showAssetPicker = false"></div>
      <div class="relative bg-white w-full max-w-4xl h-[85vh] rounded-xl shadow-2xl flex flex-col">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between shrink-0">
          <h2 class="text-xl font-bold text-slate-900">选择资产</h2>
          <button @click="showAssetPicker = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="flex-1 flex overflow-hidden">
          <!-- Left: Org Tree -->
          <div class="w-64 border-r border-slate-100 overflow-y-auto p-4 shrink-0">
            <a-tree
              :tree-data="[
                { id: null, title: 'Default', key: '__all__', children: orgTreeData },
              ]"
              :selected-keys="[String(pickerSelectedOrgId ?? '__all__')]"
              @select="onPickerTreeSelect"
              show-line
              default-expand-all
            />
          </div>
          <!-- Right: Asset List -->
          <div class="flex-1 flex flex-col overflow-hidden">
            <!-- Search bar -->
            <div class="p-4 border-b border-slate-100 shrink-0">
              <a-input-search
                v-model:value="pickerSearch"
                placeholder="搜索资产名称或类型..."
                allow-clear
              />
            </div>
            <!-- Asset list -->
            <div class="flex-1 overflow-y-auto">
              <table class="w-full">
                <thead class="sticky top-0 bg-slate-50 z-10">
                  <tr>
                    <th class="text-left text-xs font-medium text-slate-500 px-4 py-2" style="width:40px;"></th>
                    <th class="text-left text-xs font-medium text-slate-500 px-4 py-2">名称</th>
                    <th class="text-left text-xs font-medium text-slate-500 px-4 py-2">类型</th>
                    <th class="text-left text-xs font-medium text-slate-500 px-4 py-2">地址</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="pickerAssets.length === 0">
                    <td colspan="4" class="text-center py-8 text-slate-400">暂无资产</td>
                  </tr>
                  <tr
                    v-for="asset in pickerAssets"
                    :key="asset.id"
                    @click="togglePickerAsset(asset.id)"
                    class="cursor-pointer hover:bg-primary/5 transition-colors"
                    :class="{ 'bg-primary/5': pickerSelectedAssetIds.includes(asset.id) }"
                  >
                    <td class="px-4 py-2.5" @click.stop>
                      <a-checkbox
                        :checked="pickerSelectedAssetIds.includes(asset.id)"
                        @change="togglePickerAsset(asset.id)"
                      />
                    </td>
                    <td class="px-4 py-2.5 text-sm font-medium text-slate-900">{{ asset.name }}</td>
                    <td class="px-4 py-2.5 text-sm text-slate-500">{{ asset.category }}</td>
                    <td class="px-4 py-2.5 text-sm text-slate-500">
                      <div v-if="asset.external_address" class="text-sm text-slate-600 font-mono">
                        <span class="text-[10px] text-blue-500 font-medium mr-1">外</span>
                        <span v-text="asset.external_address"></span>
                      </div>
                      <div v-if="asset.internal_address" class="text-sm text-slate-600 font-mono">
                        <span class="text-[10px] text-green-500 font-medium mr-1">内</span>
                        <span v-text="asset.internal_address"></span>
                      </div>
                      <span v-if="!asset.external_address && !asset.internal_address" class="text-sm text-slate-400">-</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <!-- Footer: Confirm/Cancel -->
            <div class="shrink-0 px-4 py-3 border-t border-slate-100 flex items-center justify-between bg-slate-50 rounded-b-xl">
              <span class="text-sm text-slate-500">已选 {{ pickerSelectedAssetIds.length }} 个资产</span>
              <div class="flex items-center gap-2">
                <button @click="cancelPickerSelection" class="btn-secondary">取消</button>
                <button @click="confirmPickerSelection" class="btn-primary">确认</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>