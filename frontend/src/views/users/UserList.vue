<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import { getUsers, createUser, updateUser, deleteUser, resetUserPassword } from '@/api/users'
import { getGroups } from '@/api/users'
import type { User, Group } from '@/types'

// Data
const users = ref<User[]>([])
const groups = ref<Group[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const limit = ref(20)

// Filters
const searchQuery = ref('')
const statusFilter = ref<boolean | null>(null)

// Modal states
const showUserModal = ref(false)
const showResetPasswordModal = ref(false)
const modalLoading = ref(false)
const editingUser = ref<User | null>(null)
const resetPasswordUser = ref<User | null>(null)

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
    const result = await getUsers({
      page: page.value,
      limit: limit.value,
      search: searchQuery.value || undefined,
      is_active: statusFilter.value ?? undefined
    })
    users.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    message.error('获取用户列表失败')
    users.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// Fetch groups for dropdown
async function fetchGroups() {
  try {
    const result = await getGroups({ limit: 100 })
    groups.value = result.items || []
  } catch (error) {
    console.error('Failed to fetch groups')
    groups.value = []
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
  showUserModal.value = true
}

// Submit user form
async function handleSubmit() {
  if (!userForm.value.username || !userForm.value.email) {
    message.error('请填写必填字段')
    return
  }

  if (!editingUser.value && userForm.value.password !== userForm.value.confirm_password) {
    message.error('两次输入的密码不一致')
    return
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
  if (!confirm(`确定要删除用户 "${user.username}" 吗?`)) return

  try {
    await deleteUser(user.id)
    message.success('用户已删除')
    fetchUsers()
  } catch (error) {
    message.error('删除失败')
  }
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

// Initial load
onMounted(() => {
  fetchUsers()
  fetchGroups()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">用户列表</h1>
        <p class="text-slate-500 mt-1">管理企业架构中的所有系统访问用户及其权限角色</p>
      </div>
      <button @click="openCreateModal" class="btn-primary flex items-center gap-2">
        <span class="material-symbols-outlined">person_add</span>
        添加用户
      </button>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-4">
        <div class="relative flex-1 max-w-md">
          <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">search</span>
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
                <button @click="openEditModal(user)" class="p-1.5 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600" title="编辑">
                  <span class="material-symbols-outlined text-lg">edit</span>
                </button>
                <button @click="openResetPasswordModal(user)" class="p-1.5 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600" title="重置密码">
                  <span class="material-symbols-outlined text-lg">lock_reset</span>
                </button>
                <button @click="handleDelete(user)" class="p-1.5 hover:bg-red-50 rounded text-slate-400 hover:text-red-600" title="删除">
                  <span class="material-symbols-outlined text-lg">delete</span>
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
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleSubmit" class="space-y-4">
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
                <input v-model="userForm.email" type="email" class="input-field" placeholder="请输入邮箱" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">姓名</label>
                <input v-model="userForm.full_name" type="text" class="input-field" placeholder="请输入姓名" />
              </div>
            </div>

            <!-- Phone -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">手机号</label>
              <input v-model="userForm.phone" type="text" class="input-field" placeholder="请输入手机号" />
            </div>

            <!-- Groups -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">用户组</label>
              <select v-model="userForm.group_ids" multiple class="input-field h-auto min-h-[80px]">
                <option v-for="group in groups" :key="group.id" :value="group.id">
                  {{ group.name }}
                </option>
              </select>
              <p class="text-xs text-slate-500 mt-1">按住 Ctrl/Cmd 可多选</p>
            </div>

            <!-- Password (only for create) -->
            <template v-if="!editingUser">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">密码 <span class="text-red-500">*</span></label>
                  <input v-model="userForm.password" type="password" class="input-field" placeholder="请输入密码" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">确认密码 <span class="text-red-500">*</span></label>
                  <input v-model="userForm.confirm_password" type="password" class="input-field" placeholder="请再次输入密码" />
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
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleResetPassword" class="space-y-4">
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
                <input v-model="resetPasswordForm.new_password" type="password" class="input-field" placeholder="请输入新密码" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">确认密码</label>
                <input v-model="resetPasswordForm.confirm_password" type="password" class="input-field" placeholder="请再次输入密码" />
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
  </div>
</template>