<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { UserAddOutlined, SearchOutlined, SafetyCertificateOutlined, EditOutlined, LockOutlined, DeleteOutlined, CloseOutlined } from '@ant-design/icons-vue'
import { createUser, updateUser, deleteUser, resetUserPassword, getUserAuthorizations, getGroups } from '@/api/users'
import { useUsersStore } from '@/stores/users'
import type { User, UserAuthorization } from '@/types'

const router = useRouter()
const route = useRoute()
const usersStore = useUsersStore()

// Data — use store for shared state
const users = computed(() => usersStore.users)
const groups = computed(() => usersStore.groups)
const total = computed(() => usersStore.usersTotal)
const page = computed({
  get: () => usersStore.usersPage,
  set: (v: number) => { usersStore.usersPage = v },
})
const limit = computed({
  get: () => usersStore.usersLimit,
  set: (v: number) => { usersStore.usersLimit = v },
})
const loading = ref(false)

// Filters
const searchQuery = ref('')
const statusFilter = ref<boolean | null>(null)

// Modal states
const showUserModal = ref(false)
const showResetPasswordModal = ref(false)
const showAuthorizationsModal = ref(false)
const modalLoading = ref(false)
const editingUser = ref<User | null>(null)
const resetPasswordUser = ref<User | null>(null)
const authUser = ref<User | null>(null)
const authorizations = ref<UserAuthorization[]>([])
const authorizationsLoading = ref(false)

// Form state
const userForm = ref({
  username: '',
  email: '',
  full_name: '',
  phone: '',
  password: '',
  confirm_password: '',
  group_ids: [] as number[],
  is_active: true,
  mfa_enabled: false
})

// Validation
const emailError = ref('')
const phoneError = ref('')
const passwordStrength = ref<'weak' | 'medium' | 'strong' | ''>('')

function validateEmail(email: string): boolean {
  if (!email) return true
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(email)
}

function validatePhone(phone: string): boolean {
  if (!phone) return true
  const re = /^1[3-9]\d{9}$/
  return re.test(phone)
}

function getPasswordStrength(password: string): 'weak' | 'medium' | 'strong' | '' {
  if (!password) return ''
  let score = 0
  if (password.length >= 8) score++
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++
  if (/\d/.test(password)) score++
  if (/[^a-zA-Z0-9]/.test(password)) score++
  if (score <= 1) return 'weak'
  if (score <= 2) return 'medium'
  return 'strong'
}

function onEmailBlur() {
  if (userForm.value.email && !validateEmail(userForm.value.email)) {
    emailError.value = '请输入有效的邮箱地址'
  } else {
    emailError.value = ''
  }
}

function onPhoneBlur() {
  if (userForm.value.phone && !validatePhone(userForm.value.phone)) {
    phoneError.value = '请输入有效的中国大陆手机号'
  } else {
    phoneError.value = ''
  }
}

function onPasswordInput() {
  passwordStrength.value = getPasswordStrength(userForm.value.password)
}

const resetPasswordForm = ref({
  method: 'auto' as 'auto' | 'manual',
  new_password: '',
  confirm_password: '',
  force_change: true
})

// Computed
const modalTitle = computed(() => editingUser.value ? '编辑用户' : '添加用户')

// Fetch users
async function fetchUsers() {
  loading.value = true
  try {
    await usersStore.fetchUsers({
      page: page.value,
      limit: limit.value,
      search: searchQuery.value || undefined,
      is_active: statusFilter.value ?? undefined
    })
  } catch (error: any) {
    message.error(error.response?.data?.detail || '获取用户列表失败')
    usersStore.resetUsers()
  } finally {
    loading.value = false
  }
}

// Fetch groups for dropdown
async function fetchGroups() {
  try {
    const result = await getGroups({ limit: 100 })
    usersStore.groups = result.items || []
  } catch (error) {
    console.error('Failed to fetch groups')
    usersStore.groups = []
  }
}

// Handle search
function handleSearch() {
  page.value = 1
  fetchUsers()
}

// Handle page change
function handlePageChange(newPage: number) {
  page.value = newPage
  fetchUsers()
}

// Open create modal
function openCreateModal() {
  editingUser.value = null
  userForm.value = {
    username: '',
    email: '',
    full_name: '',
    phone: '',
    password: '',
    confirm_password: '',
    group_ids: [],
    is_active: true,
    mfa_enabled: false
  }
  emailError.value = ''
  phoneError.value = ''
  passwordStrength.value = ''
  groupSearch.value = ''
  showGroupDropdown.value = false
  showUserModal.value = true
}

// Open edit modal
function openEditModal(user: User) {
  editingUser.value = user
  userForm.value = {
    username: user.username,
    email: user.email,
    full_name: user.full_name || '',
    phone: user.phone || '',
    password: '',
    confirm_password: '',
    group_ids: user.groups?.map(g => g.id) || [],
    is_active: user.is_active,
    mfa_enabled: user.mfa_enabled
  }
  emailError.value = ''
  phoneError.value = ''
  passwordStrength.value = ''
  groupSearch.value = ''
  showGroupDropdown.value = false
  showUserModal.value = true
}

// Submit user form
async function handleSubmit() {
  if (!userForm.value.username || !userForm.value.email) {
    message.error('请填写必填字段')
    return
  }

  if (!validateEmail(userForm.value.email)) {
    emailError.value = '请输入有效的邮箱地址'
    return
  }

  if (userForm.value.phone && !validatePhone(userForm.value.phone)) {
    phoneError.value = '请输入有效的中国大陆手机号'
    return
  }

  if (!editingUser.value) {
    if (!userForm.value.password) {
      message.error('请输入密码')
      return
    }
    if (userForm.value.password !== userForm.value.confirm_password) {
      message.error('两次输入的密码不一致')
      return
    }
  }

  modalLoading.value = true
  try {
    if (editingUser.value) {
      // Update user
      await updateUser(editingUser.value.id, {
        email: userForm.value.email,
        full_name: userForm.value.full_name,
        phone: userForm.value.phone,
        group_ids: userForm.value.group_ids,
        is_active: userForm.value.is_active,
        mfa_enabled: userForm.value.mfa_enabled
      })
      message.success('用户更新成功')
    } else {
      // Create user
      await createUser({
        username: userForm.value.username,
        email: userForm.value.email,
        password: userForm.value.password,
        full_name: userForm.value.full_name,
        phone: userForm.value.phone,
        group_ids: userForm.value.group_ids,
        is_active: userForm.value.is_active,
        mfa_enabled: userForm.value.mfa_enabled
      })
      message.success('用户创建成功')
    }
    showUserModal.value = false
    fetchUsers()
  } catch (error: any) {
    message.error(error.response?.data?.detail || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

// Delete user
async function handleDelete(user: User) {
  Modal.confirm({
    title: '删除用户',
    content: `确定要删除用户 "${user.username}" 吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deleteUser(user.id)
        message.success('用户已删除')
        fetchUsers()
      } catch (e: any) {
        message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

// Open reset password modal
function openResetPasswordModal(user: User) {
  resetPasswordUser.value = user
  resetPasswordForm.value = {
    method: 'auto',
    new_password: '',
    confirm_password: '',
    force_change: true
  }
  showResetPasswordModal.value = true
}

// Submit reset password
async function handleResetPassword() {
  if (!resetPasswordUser.value) return

  if (resetPasswordForm.value.method === 'manual') {
    if (resetPasswordForm.value.new_password !== resetPasswordForm.value.confirm_password) {
      message.error('两次输入的密码不一致')
      return
    }
    if (resetPasswordForm.value.new_password.length < 8) {
      message.error('密码长度不能少于8个字符')
      return
    }
  }

  modalLoading.value = true
  try {
    const result = await resetUserPassword(resetPasswordUser.value.id, {
      method: resetPasswordForm.value.method,
      new_password: resetPasswordForm.value.method === 'manual' ? resetPasswordForm.value.new_password : undefined,
      force_change: resetPasswordForm.value.force_change
    })

    showResetPasswordModal.value = false
    if (resetPasswordForm.value.method === 'auto' && result.temp_password) {
      message.success(`密码重置成功，临时密码: ${result.temp_password}`)
    } else {
      message.success('密码重置成功')
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || '重置失败')
  } finally {
    modalLoading.value = false
  }
}

// Get user avatar text
function getAvatarText(user: User): string {
  return user.full_name?.[0] || user.username[0]?.toUpperCase() || 'U'
}

// Format date
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// Asset category labels
const categoryLabels: Record<string, string> = {
  host: '主机',
  network: '网络设备',
  database: '数据库',
  cloud: '云服务',
  web: '网站服务',
  gpt: 'AI服务'
}

// Permission labels
const permissionLabels: Record<string, string> = {
  view: '查看资产',
  manage: '管理资产',
  user_mgmt: '用户管理',
  sys_config: '系统设置',
  audit_log: '日志审计',
  view_pwd: '查看密码',
  manage_pwd: '管理密码'
}

// Open authorizations modal
async function openAuthorizationsModal(user: User) {
  authUser.value = user
  authorizations.value = []
  authorizationsLoading.value = true
  showAuthorizationsModal.value = true

  try {
    const result = await getUserAuthorizations(user.id)
    // Combine direct and inherited authorizations
    authorizations.value = [...result.direct, ...result.inherited]
  } catch (error) {
    message.error('获取授权列表失败')
    authorizations.value = []
  } finally {
    authorizationsLoading.value = false
  }
}

// Group multi-select state
const groupSearch = ref('')
const showGroupDropdown = ref(false)
const groupDropdownRef = ref<HTMLElement | null>(null)

// Filtered groups (exclude already selected)
const availableGroups = computed(() => {
  const selectedIds = new Set(userForm.value.group_ids)
  return groups.value.filter(g =>
    !selectedIds.has(g.id) &&
    (groupSearch.value === '' || g.name.toLowerCase().includes(groupSearch.value.toLowerCase()))
  )
})

function isSelected(groupId: number): boolean {
  return userForm.value.group_ids.includes(groupId)
}

function removeGroup(groupId: number) {
  userForm.value.group_ids = userForm.value.group_ids.filter(id => id !== groupId)
}

function addGroup(groupId: number) {
  if (!isSelected(groupId)) {
    userForm.value.group_ids.push(groupId)
  }
  groupSearch.value = ''
}

// Close dropdown on outside click
function onGroupInputClick(e: Event) {
  e.stopPropagation()
  showGroupDropdown.value = true
  groupSearch.value = ''
}

function onGroupDropdownClick(e: Event) {
  e.stopPropagation()
}

function onDocumentClick() {
  showGroupDropdown.value = false
}

// Initial load
onMounted(() => {
  document.addEventListener('click', onDocumentClick)

  // Restore state from URL
  const query = route.query
  if (query.page) usersStore.usersPage = Number(query.page)
  if (query.search) searchQuery.value = query.search as string
  if (query.status === 'true') statusFilter.value = true
  else if (query.status === 'false') statusFilter.value = false

  fetchUsers()
  fetchGroups()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
})

// Sync state to URL
watch([() => usersStore.usersPage, searchQuery, statusFilter], () => {
  const query: Record<string, string> = {}
  if (usersStore.usersPage !== 1) query.page = String(usersStore.usersPage)
  if (searchQuery.value) query.search = searchQuery.value
  if (statusFilter.value !== null) query.status = String(statusFilter.value)
  router.replace({ query })
}, { deep: true })
</script>

<template>
  <div class="space-y-4">
    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-4">
        <button @click="openCreateModal" class="btn-primary flex items-center gap-2">
          <UserAddOutlined />
          添加用户
        </button>
        <div class="relative flex-1 max-w-md">
          <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索用户名、姓名、邮箱..."
            class="input-field pl-10"
            @keyup.enter="handleSearch"
          />
        </div>
        <select v-model="statusFilter" @change="handleSearch" class="input-field w-32">
          <option :value="null">全部状态</option>
          <option :value="true">活跃</option>
          <option :value="false">禁用</option>
        </select>
        <button @click="handleSearch" class="btn-secondary">搜索</button>
      </div>
    </div>

    <!-- User Table -->
    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <table class="data-table">
        <thead>
          <tr>
            <th>用户名</th>
            <th>姓名</th>
            <th>邮箱</th>
            <th>用户组</th>
            <th>最后登录</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7" class="text-center py-8 text-slate-500">加载中...</td>
          </tr>
          <tr v-else-if="users.length === 0">
            <td colspan="7" class="text-center py-8 text-slate-500">暂无数据</td>
          </tr>
          <tr v-for="user in users" :key="user.id">
            <td>
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">
                  <span class="text-primary font-medium text-sm">{{ getAvatarText(user) }}</span>
                </div>
                <span class="font-medium text-slate-900">{{ user.username }}</span>
              </div>
            </td>
            <td>
              <span class="text-slate-600">{{ user.full_name || '-' }}</span>
            </td>
            <td>
              <span class="text-slate-600">{{ user.email }}</span>
            </td>
            <td>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="group in user.groups"
                  :key="group.id"
                  class="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-md font-medium"
                >
                  {{ group.name }}
                </span>
                <span v-if="!user.groups?.length" class="text-slate-400">-</span>
              </div>
            </td>
            <td>
              <span class="text-sm text-slate-600">{{ formatDate(user.last_login_at) }}</span>
            </td>
            <td>
              <span
                class="badge"
                :class="user.is_active ? 'badge-success' : 'bg-slate-100 text-slate-500'"
              >
                <span class="inline-block w-1.5 h-1.5 rounded-full mr-1" :class="user.is_active ? 'bg-success' : 'bg-slate-400'"></span>
                {{ user.is_active ? 'Active' : 'Disabled' }}
              </span>
            </td>
            <td>
              <div class="flex items-center gap-1">
                <button @click="openAuthorizationsModal(user)" class="text-xs text-primary hover:underline flex items-center gap-1 mr-2" title="已授权资产">
                  <SafetyCertificateOutlined class="text-sm" />
                  授权
                </button>
                <button @click="openEditModal(user)" class="p-1.5 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600" title="编辑">
                  <EditOutlined class="text-lg" />
                </button>
                <button @click="openResetPasswordModal(user)" class="p-1.5 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600" title="重置密码">
                  <LockOutlined class="text-lg" />
                </button>
                <button @click="handleDelete(user)" class="p-1.5 hover:bg-red-50 rounded text-slate-400 hover:text-red-600" title="删除">
                  <DeleteOutlined class="text-lg" />
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
          <span class="text-sm text-slate-600">{{ page }} / {{ Math.ceil(total / limit) }}</span>
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

    <!-- User Modal -->
    <div v-if="showUserModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showUserModal = false"></div>
      <div class="relative bg-white w-full max-w-2xl rounded-xl shadow-2xl max-h-[90vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">{{ modalTitle }}</h2>
          <button @click="showUserModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleSubmit" autocomplete="off" class="space-y-4">
            <!-- Username (readonly for edit) -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">用户名 <span class="text-red-500">*</span></label>
              <input
                v-model="userForm.username"
                type="text"
                :disabled="!!editingUser"
                class="input-field"
                :class="editingUser ? 'bg-slate-50 text-slate-500' : ''"
                placeholder="请输入用户名"
              />
            </div>

            <!-- Email & Full Name -->
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">邮箱 <span class="text-red-500">*</span></label>
                <input v-model="userForm.email" type="email" class="input-field" :class="{ 'border-red-400': emailError }" placeholder="请输入邮箱" @blur="onEmailBlur" />
                <p v-if="emailError" class="text-xs text-red-500 mt-1">{{ emailError }}</p>
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">姓名</label>
                <input v-model="userForm.full_name" type="text" class="input-field" placeholder="请输入姓名" />
              </div>
            </div>

            <!-- Phone -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">手机号</label>
              <input v-model="userForm.phone" type="text" class="input-field" :class="{ 'border-red-400': phoneError }" placeholder="请输入手机号" @blur="onPhoneBlur" />
              <p v-if="phoneError" class="text-xs text-red-500 mt-1">{{ phoneError }}</p>
            </div>

            <!-- Groups -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">用户组</label>
              <div class="relative" ref="groupDropdownRef">
                <div
                  class="bg-surface-container-lowest rounded-lg border border-slate-200 hover:border-slate-300 focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/20 transition-all cursor-text min-h-[42px] px-2 py-1 flex flex-wrap items-center gap-1"
                  @click="onGroupInputClick"
                >
                  <span
                    v-for="groupId in userForm.group_ids"
                    :key="groupId"
                    class="inline-flex items-center gap-1 bg-primary/10 text-primary text-xs font-medium px-2 py-0.5 rounded-md"
                  >
                    {{ groups.find(g => g.id === groupId)?.name || `#${groupId}` }}
                    <button
                      type="button"
                      @click.stop="removeGroup(groupId)"
                      class="hover:text-primary transition-colors font-bold leading-none"
                    >
                      ×
                    </button>
                  </span>
                  <input
                    v-model="groupSearch"
                    type="search"
                    autocomplete="section-1"
                    class="outline-none flex-1 min-w-[120px] text-sm bg-transparent"
                    :placeholder="userForm.group_ids.length === 0 ? '搜索或选择用户组' : ''"
                    @click.stop="showGroupDropdown = true"
                    @input="showGroupDropdown = true"
                  />
                </div>
                <transition name="dropdown">
                  <div
                    v-if="showGroupDropdown && availableGroups.length > 0"
                    class="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg border border-slate-200 shadow-lg max-h-48 overflow-y-auto z-50"
                    @click="onGroupDropdownClick"
                  >
                    <div
                      v-for="group in availableGroups"
                      :key="group.id"
                      class="px-3 py-2 text-sm cursor-pointer hover:bg-primary/5 transition-colors"
                      @click="addGroup(group.id)"
                    >
                      <span class="font-medium text-slate-700">{{ group.name }}</span>
                      <span v-if="group.description" class="text-slate-400 ml-2 text-xs">{{ group.description }}</span>
                    </div>
                  </div>
                </transition>
              </div>
            </div>

            <!-- Password (only for create) -->
            <template v-if="!editingUser">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">密码 <span class="text-red-500">*</span></label>
                  <input v-model="userForm.password" type="password" autocomplete="new-password" class="input-field" placeholder="请输入密码" @input="onPasswordInput" />
                  <div v-if="passwordStrength" class="mt-1.5 h-1 rounded-full bg-slate-100 overflow-hidden">
                    <div class="h-full rounded-full transition-all duration-300"
                         :class="{ 'bg-red-400 w-1/4': passwordStrength === 'weak', 'bg-yellow-400 w-1/2': passwordStrength === 'medium', 'bg-green-400 w-3/4': passwordStrength === 'strong' }" />
                  </div>
                  <p v-if="passwordStrength" class="text-xs mt-1"
                     :class="{ 'text-red-400': passwordStrength === 'weak', 'text-yellow-500': passwordStrength === 'medium', 'text-green-500': passwordStrength === 'strong' }">
                    密码强度：{{ passwordStrength === 'weak' ? '弱' : passwordStrength === 'medium' ? '中' : '强' }}
                  </p>
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">确认密码 <span class="text-red-500">*</span></label>
                  <input v-model="userForm.confirm_password" type="password" autocomplete="new-password" class="input-field" placeholder="请再次输入密码" />
                </div>
              </div>
            </template>

            <!-- Status & MFA -->
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">状态</label>
                <div class="flex gap-4 mt-2">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" v-model="userForm.is_active" :value="true" class="text-primary" />
                    <span class="text-sm text-slate-600">活跃</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" v-model="userForm.is_active" :value="false" class="text-primary" />
                    <span class="text-sm text-slate-600">禁用</span>
                  </label>
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">MFA</label>
                <div class="flex gap-4 mt-2">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" v-model="userForm.mfa_enabled" :value="true" class="text-primary" />
                    <span class="text-sm text-slate-600">开启</span>
                  </label>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" v-model="userForm.mfa_enabled" :value="false" class="text-primary" />
                    <span class="text-sm text-slate-600">关闭</span>
                  </label>
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex justify-end gap-2 pt-4">
              <button type="button" @click="showUserModal = false" class="btn-secondary">取消</button>
              <button type="submit" :disabled="modalLoading" class="btn-primary">
                {{ modalLoading ? '处理中...' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Reset Password Modal -->
    <div v-if="showResetPasswordModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showResetPasswordModal = false"></div>
      <div class="relative bg-white w-full max-w-md rounded-xl shadow-2xl">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">重置密码 - {{ resetPasswordUser?.full_name || resetPasswordUser?.username }}</h2>
          <button @click="showResetPasswordModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleResetPassword" autocomplete="off" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">重置方式</label>
              <div class="space-y-2 mt-2">
                <label class="flex items-start gap-3 cursor-pointer p-3 border rounded-lg" :class="resetPasswordForm.method === 'auto' ? 'border-primary bg-primary/5' : 'border-slate-200'">
                  <input type="radio" v-model="resetPasswordForm.method" value="auto" class="mt-0.5" />
                  <div>
                    <span class="text-sm font-medium text-slate-700">自动生成密码并发送邮件</span>
                    <p class="text-xs text-slate-500 mt-1">系统将生成随机密码并发送到用户邮箱</p>
                  </div>
                </label>
                <label class="flex items-start gap-3 cursor-pointer p-3 border rounded-lg" :class="resetPasswordForm.method === 'manual' ? 'border-primary bg-primary/5' : 'border-slate-200'">
                  <input type="radio" v-model="resetPasswordForm.method" value="manual" class="mt-0.5" />
                  <div>
                    <span class="text-sm font-medium text-slate-700">手动设置新密码</span>
                  </div>
                </label>
              </div>
            </div>

            <template v-if="resetPasswordForm.method === 'manual'">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">新密码</label>
                <input v-model="resetPasswordForm.new_password" type="password" autocomplete="new-password" class="input-field" placeholder="请输入新密码" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">确认密码</label>
                <input v-model="resetPasswordForm.confirm_password" type="password" autocomplete="new-password" class="input-field" placeholder="请再次输入密码" />
              </div>
            </template>

            <div class="flex items-center gap-2">
              <input type="checkbox" v-model="resetPasswordForm.force_change" id="force_change" />
              <label for="force_change" class="text-sm text-slate-600">强制用户首次登录修改密码</label>
            </div>

            <div class="flex justify-end gap-2 pt-4">
              <button type="button" @click="showResetPasswordModal = false" class="btn-secondary">取消</button>
              <button type="submit" :disabled="modalLoading" class="btn-primary">
                {{ modalLoading ? '处理中...' : '重置密码' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Authorizations Modal -->
    <div v-if="showAuthorizationsModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showAuthorizationsModal = false"></div>
      <div class="relative bg-white w-full max-w-3xl rounded-xl shadow-2xl max-h-[80vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">已授权资产 - {{ authUser?.full_name || authUser?.username }}</h2>
          <button @click="showAuthorizationsModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <div v-if="authorizationsLoading" class="text-center py-8 text-slate-500">加载中...</div>
          <div v-else-if="authorizations.length === 0" class="text-center py-8 text-slate-500">暂无授权记录</div>
          <table v-else class="data-table">
            <thead>
              <tr>
                <th>资产名称</th>
                <th>资产类型</th>
                <th>权限</th>
                <th>授权来源</th>
                <th>有效期</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="auth in authorizations" :key="auth.id">
                <td>
                  <span class="font-medium text-slate-900">{{ auth.asset_name }}</span>
                </td>
                <td>
                  <span class="text-sm text-slate-600">{{ categoryLabels[auth.asset_category] || auth.asset_category }}</span>
                </td>
                <td>
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="perm in auth.permissions"
                      :key="perm"
                      class="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded font-medium"
                    >
                      {{ permissionLabels[perm] || perm }}
                    </span>
                  </div>
                </td>
                <td>
                  <span v-if="auth.source_type === 'direct'" class="text-xs text-primary">直接授权</span>
                  <span v-else class="text-xs text-slate-500">用户组: {{ auth.group_name }}</span>
                </td>
                <td>
                  <span class="text-sm text-slate-600">{{ auth.valid_until ? formatDate(auth.valid_until) : '永久' }}</span>
                </td>
                <td>
                  <span class="badge badge-success">
                    <span class="inline-block w-1.5 h-1.5 rounded-full mr-1 bg-success"></span>
                    {{ auth.status === 'active' ? 'Active' : 'Inactive' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="flex justify-end mt-4">
            <button @click="showAuthorizationsModal = false" class="btn-secondary">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>