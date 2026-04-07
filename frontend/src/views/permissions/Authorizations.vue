<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, EditOutlined, BlockOutlined, CheckCircleOutlined, DeleteOutlined, CloseOutlined } from '@ant-design/icons-vue'
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

// Form
const form = ref({
  entity_type: 'user' as 'user' | 'group',
  entity_id: null as number | null,
  target_type: 'asset' as 'asset' | 'organization',
  target_id: null as number | null,
  permissions: [] as string[],
  valid_until: ''
})

// Selection options
const users = ref<Array<{ id: number; name: string; full_name: string | null }>>([])
const groups = ref<Array<{ id: number; name: string }>>([])
const assets = ref<Array<{ id: number; name: string; category: string }>>([])
const organizations = ref<Array<{ id: number; name: string; path: string | null }>>([])

// Search filters for modal
const userSearch = ref('')
const groupSearch = ref('')
const assetSearch = ref('')
const orgSearch = ref('')

// Computed filtered lists
const filteredUsers = computed(() => {
  if (!userSearch.value) return users.value
  const search = userSearch.value.toLowerCase()
  return users.value.filter(u =>
    u.name.toLowerCase().includes(search) ||
    (u.full_name && u.full_name.toLowerCase().includes(search))
  )
})

const filteredGroups = computed(() => {
  if (!groupSearch.value) return groups.value
  return groups.value.filter(g => g.name.toLowerCase().includes(groupSearch.value.toLowerCase()))
})

const filteredAssets = computed(() => {
  if (!assetSearch.value) return assets.value
  const search = assetSearch.value.toLowerCase()
  return assets.value.filter(a =>
    a.name.toLowerCase().includes(search) ||
    a.category.toLowerCase().includes(search)
  )
})

const filteredOrgs = computed(() => {
  if (!orgSearch.value) return organizations.value
  const search = orgSearch.value.toLowerCase()
  return organizations.value.filter(o =>
    o.name.toLowerCase().includes(search) ||
    (o.path && o.path.toLowerCase().includes(search))
  )
})

// Permission options
const permissionOptions = [
  { key: 'view', label: '查看资产' },
  { key: 'manage', label: '管理资产' },
  { key: 'user_mgmt', label: '用户管理' },
  { key: 'sys_config', label: '系统设置' },
  { key: 'audit_log', label: '日志审计' },
  { key: 'view_pwd', label: '查看密码' },
  { key: 'manage_pwd', label: '管理凭证' }
]

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

// Fetch selection options
async function fetchSelectionOptions() {
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
  } catch {
    // Handle silently
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
    target_id: null,
    permissions: [],
    valid_until: ''
  }
  // Clear search filters
  userSearch.value = ''
  groupSearch.value = ''
  assetSearch.value = ''
  orgSearch.value = ''
  showModal.value = true
}

// Open edit modal
function openEditModal(auth: any) {
  isEditMode.value = true
  editingAuthId.value = auth.id
  form.value = {
    entity_type: auth.entity_type,
    entity_id: auth.entity_id,
    target_type: auth.target_type,
    target_id: auth.target_id,
    permissions: auth.permissions || [],
    valid_until: auth.valid_until ? auth.valid_until.slice(0, 16) : ''
  }
  // Clear search filters
  userSearch.value = ''
  groupSearch.value = ''
  assetSearch.value = ''
  orgSearch.value = ''
  showModal.value = true
}

// Submit form
async function handleSubmit() {
  if (!isEditMode.value) {
    if (!form.value.entity_id) {
      message.error('请选择授权对象')
      return
    }
    if (!form.value.target_id) {
      message.error('请选择资产')
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
      await updateAuthorization(editingAuthId.value, updateData)
      message.success('授权更新成功')
    } else {
      // Create new authorization
      const data: AuthorizationCreate = {
        entity_type: form.value.entity_type,
        entity_id: form.value.entity_id!,
        target_type: form.value.target_type,
        target_id: form.value.target_id!,
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
  if (!confirm(`确定要删除此授权吗?`)) return

  try {
    await deleteAuthorization(auth.id)
    message.success('授权已删除')
    fetchAuthorizations()
  } catch {
    message.error('删除失败')
  }
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

// Format datetime
function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
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
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">资产授权</h1>
        <p class="text-slate-500 mt-1">管理和维护系统资产与用户/用户组之间的权限关系</p>
      </div>
      <button @click="openCreateModal" class="btn-primary flex items-center gap-2">
        <PlusOutlined />
        新增授权
      </button>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-4 flex-wrap">
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
              <div class="relative">
                <input
                  v-if="form.entity_type === 'user'"
                  type="text"
                  v-model="userSearch"
                  placeholder="搜索用户..."
                  class="input-field mb-2"
                />
                <input
                  v-else
                  type="text"
                  v-model="groupSearch"
                  placeholder="搜索用户组..."
                  class="input-field mb-2"
                />
                <select v-model="form.entity_id" class="input-field">
                  <option :value="null">请选择{{ form.entity_type === 'user' ? '用户' : '用户组' }}</option>
                  <template v-if="form.entity_type === 'user'">
                    <option v-for="user in filteredUsers" :key="user.id" :value="user.id">
                      {{ user.name }}{{ user.full_name ? ` (${user.full_name})` : '' }}
                    </option>
                  </template>
                  <template v-else>
                    <option v-for="group in filteredGroups" :key="group.id" :value="group.id">
                      {{ group.name }}
                    </option>
                  </template>
                </select>
              </div>
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

            <!-- Target Selection (disabled in edit mode) -->
            <div v-if="!isEditMode">
              <label class="block text-sm font-medium text-slate-700 mb-2">资产范围</label>
              <div class="flex gap-4 mb-3">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="radio" v-model="form.target_type" value="asset" class="text-primary" />
                  <span class="text-sm">单个资产</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="radio" v-model="form.target_type" value="organization" class="text-primary" />
                  <span class="text-sm">组织</span>
                </label>
              </div>
              <div class="relative">
                <input
                  v-if="form.target_type === 'asset'"
                  type="text"
                  v-model="assetSearch"
                  placeholder="搜索资产..."
                  class="input-field mb-2"
                />
                <input
                  v-else
                  type="text"
                  v-model="orgSearch"
                  placeholder="搜索组织..."
                  class="input-field mb-2"
                />
                <select v-model="form.target_id" class="input-field">
                  <option :value="null">请选择{{ form.target_type === 'asset' ? '资产' : '组织' }}</option>
                  <template v-if="form.target_type === 'asset'">
                    <option v-for="item in filteredAssets" :key="item.id" :value="item.id">
                      {{ item.name }} ({{ item.category }})
                    </option>
                  </template>
                  <template v-else>
                    <option v-for="item in filteredOrgs" :key="item.id" :value="item.id">
                      {{ item.name }}{{ item.path ? ` - ${item.path}` : '' }}
                    </option>
                  </template>
                </select>
              </div>
            </div>

            <!-- Show target info in edit mode -->
            <div v-else>
              <label class="block text-sm font-medium text-slate-700 mb-2">资产范围</label>
              <div class="p-3 bg-slate-50 rounded-lg">
                <p class="font-medium text-slate-900">
                  {{ form.target_type === 'asset'
                    ? assets.find(a => a.id === form.target_id)?.name
                    : organizations.find(o => o.id === form.target_id)?.name }}
                </p>
                <p class="text-sm text-slate-500">
                  {{ form.target_type === 'asset' ? '资产' : '组织' }}
                </p>
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
              <input type="datetime-local" v-model="form.valid_until" class="input-field" />
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
  </div>
</template>