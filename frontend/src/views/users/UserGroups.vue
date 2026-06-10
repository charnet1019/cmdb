<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { UsergroupAddOutlined, SearchOutlined, SafetyCertificateOutlined, GroupOutlined, EditOutlined, DeleteOutlined, CloseOutlined, UserAddOutlined, UserDeleteOutlined } from '@ant-design/icons-vue'
import { createGroup, deleteGroup, updateGroup, getGroupAuthorizations, getGroupMembers, addGroupMembers, removeGroupMember, getUsers } from '@/api/users'
import { useUsersStore } from '@/stores/users'
import type { Group, GroupAuthorization, GroupMember } from '@/types'

const router = useRouter()
const route = useRoute()
const usersStore = useUsersStore()

// Data — use store for shared state
const groups = computed(() => usersStore.groups)
const allUsers = computed(() => usersStore.allUsers)
const total = computed(() => usersStore.groupsTotal)
const page = computed({
  get: () => usersStore.groupsPage,
  set: (v: number) => { usersStore.groupsPage = v },
})
const limit = ref(20)
const loading = ref(false)

// Filters
const searchQuery = ref('')

// Modal states
const showModal = ref(false)
const showAuthModal = ref(false)
const showMembersModal = ref(false)
const showEditModal = ref(false)
const modalLoading = ref(false)

// Selected group
const selectedGroup = ref<Group | null>(null)
const groupAuthorizations = ref<GroupAuthorization[]>([])
const groupMembers = ref<GroupMember[]>([])
const authLoading = ref(false)
const membersLoading = ref(false)

// Form state
const groupForm = ref({
  name: '',
  description: '',
  initial_member_ids: [] as number[]
})

// Add members form
const selectedUserIds = ref<number[]>([])

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

// Fetch groups
async function fetchGroups() {
  loading.value = true
  try {
    await usersStore.fetchGroups({
      page: page.value,
      limit: limit.value,
      search: searchQuery.value || undefined
    })
  } catch (error: any) {
    message.error(error.response?.data?.detail || '获取用户组列表失败')
    usersStore.resetGroups()
  } finally {
    loading.value = false
  }
}

// Fetch all users for adding members
async function fetchUsers() {
  try {
    const result = await getUsers({ limit: 100 })
    usersStore.allUsers = result.items || []
  } catch {
    // Handle silently
  }
}

// Handle search
function handleSearch() {
  page.value = 1
  fetchGroups()
}

// Handle page change
function handlePageChange(newPage: number) {
  page.value = newPage
  fetchGroups()
}

// Open create modal
async function openCreateModal() {
  groupForm.value = {
    name: '',
    description: '',
    initial_member_ids: []
  }
  await fetchUsers()
  showModal.value = true
}

// Open edit modal
function openEditModal(group: Group) {
  selectedGroup.value = group
  groupForm.value = {
    name: group.name,
    description: group.description || ''
  }
  showEditModal.value = true
}

// Submit group form (create)
async function handleSubmit() {
  if (!groupForm.value.name) {
    message.error('请输入用户组名称')
    return
  }

  modalLoading.value = true
  try {
    await createGroup({
      name: groupForm.value.name,
      description: groupForm.value.description,
      initial_member_ids: groupForm.value.initial_member_ids.length > 0 ? groupForm.value.initial_member_ids : undefined
    })
    message.success('用户组创建成功')
    showModal.value = false
    fetchGroups()
  } catch (error: any) {
    message.error(error.response?.data?.detail || '创建失败')
  } finally {
    modalLoading.value = false
  }
}

// Submit edit form
async function handleEditSubmit() {
  if (!groupForm.value.name || !selectedGroup.value) {
    message.error('请输入用户组名称')
    return
  }

  modalLoading.value = true
  try {
    await updateGroup(selectedGroup.value.id, {
      name: groupForm.value.name,
      description: groupForm.value.description
    })
    message.success('用户组更新成功')
    showEditModal.value = false
    fetchGroups()
  } catch (error: any) {
    message.error(error.response?.data?.detail || '更新失败')
  } finally {
    modalLoading.value = false
  }
}

// Delete group
async function handleDelete(group: Group) {
  Modal.confirm({
    title: '删除用户组',
    content: `确定要删除用户组 "${group.name}" 吗？`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deleteGroup(group.id)
        message.success('用户组已删除')
        fetchGroups()
      } catch (e: any) {
        message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

// Open authorizations modal
async function openAuthModal(group: Group) {
  selectedGroup.value = group
  groupAuthorizations.value = []
  authLoading.value = true
  showAuthModal.value = true

  try {
    groupAuthorizations.value = await getGroupAuthorizations(group.id)
  } catch (error) {
    message.error('获取授权列表失败')
  } finally {
    authLoading.value = false
  }
}

// Open members modal
async function openMembersModal(group: Group) {
  selectedGroup.value = group
  groupMembers.value = []
  selectedUserIds.value = []
  membersLoading.value = true
  showMembersModal.value = true

  try {
    groupMembers.value = await getGroupMembers(group.id)
  } catch (error) {
    message.error('获取成员列表失败')
  } finally {
    membersLoading.value = false
  }
}

// Add members
async function handleAddMembers() {
  if (!selectedGroup.value || !selectedUserIds.value || selectedUserIds.value.length === 0) {
    message.error('请选择要添加的成员')
    return
  }

  try {
    await addGroupMembers(selectedGroup.value.id, selectedUserIds.value)
    message.success('成员添加成功')
    selectedUserIds.value = []
    groupMembers.value = await getGroupMembers(selectedGroup.value.id)
    fetchGroups()
  } catch (error: any) {
    message.error(error.response?.data?.detail || '添加失败')
  }
}

// Remove member
async function handleRemoveMember(member: GroupMember) {
  Modal.confirm({
    title: '移除成员',
    content: `确定要将 "${member.username}" 从用户组移除吗？`,
    okText: '移除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await removeGroupMember(selectedGroup.value!.id, member.id)
        message.success('成员已移除')
        groupMembers.value = groupMembers.value.filter(m => m.id !== member.id)
        fetchGroups()
      } catch {
        message.error('移除失败')
      }
    },
  })
}

// Format date
function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

// Check if user is already a member
function isMember(userId: number): boolean {
  return groupMembers.value.some(m => m.id === userId)
}

// Initial load
onMounted(() => {
  // Restore state from URL
  const query = route.query
  if (query.page) usersStore.groupsPage = Number(query.page)
  if (query.search) searchQuery.value = query.search as string

  fetchGroups()
  fetchUsers()
})

// Sync state to URL
watch([() => usersStore.groupsPage, searchQuery], () => {
  const query: Record<string, string> = {}
  if (usersStore.groupsPage !== 1) query.page = String(usersStore.groupsPage)
  if (searchQuery.value) query.search = searchQuery.value
  router.replace({ query })
}, { deep: true })
</script>

<template>
  <div class="space-y-4">
    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-4">
        <button @click="openCreateModal" class="btn-primary flex items-center gap-2">
          <UsergroupAddOutlined />
          创建用户组
        </button>
        <div class="relative flex-1 max-w-md">
          <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索用户组..."
            class="input-field pl-10"
            @keyup.enter="handleSearch"
          />
        </div>
        <button @click="handleSearch" class="btn-secondary">搜索</button>
      </div>
    </div>

    <!-- Groups Table -->
    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <table class="data-table">
        <thead>
          <tr>
            <th>用户组名称</th>
            <th>描述</th>
            <th>成员数量</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="text-center py-8 text-slate-500">加载中...</td>
          </tr>
          <tr v-else-if="groups.length === 0">
            <td colspan="5" class="text-center py-8 text-slate-500">暂无数据</td>
          </tr>
          <tr v-for="group in groups" :key="group.id">
            <td>
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded bg-primary/10 flex items-center justify-center">
                  <SafetyCertificateOutlined class="text-primary" />
                </div>
                <div>
                  <span class="font-medium text-slate-900">{{ group.name }}</span>
                  <span v-if="group.is_default" class="ml-2 px-2 py-0.5 bg-amber-50 text-amber-700 text-xs rounded-md font-medium">默认</span>
                </div>
              </div>
            </td>
            <td>
              <span class="text-slate-600">{{ group.description || '-' }}</span>
            </td>
            <td>
              <span class="px-3 py-1 rounded-full bg-secondary-container/20 text-on-secondary-container font-semibold text-sm">
                {{ group.member_count || 0 }} 人
              </span>
            </td>
            <td>
              <span class="text-sm text-slate-600">{{ formatDate(group.created_at) }}</span>
            </td>
            <td>
              <div class="flex items-center gap-2">
                <button @click="openAuthModal(group)" class="text-xs text-primary hover:underline flex items-center gap-1">
                  <SafetyCertificateOutlined class="text-sm" />
                  授权
                </button>
                <button @click="openMembersModal(group)" class="text-xs text-primary hover:underline flex items-center gap-1">
                  <GroupOutlined class="text-sm" />
                  成员
                </button>
                <button @click="openEditModal(group)" class="p-1.5 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600" title="编辑">
                  <EditOutlined class="text-lg" />
                </button>
                <button @click="handleDelete(group)" class="p-1.5 hover:bg-red-50 rounded text-slate-400 hover:text-red-600" title="删除">
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

    <!-- Create Group Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showModal = false"></div>
      <div class="relative bg-white w-full max-w-md rounded-xl shadow-2xl">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">创建用户组</h2>
          <button @click="showModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleSubmit" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">用户组名称 <span class="text-red-500">*</span></label>
              <input v-model="groupForm.name" type="text" class="input-field" placeholder="请输入用户组名称" />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">用户组描述</label>
              <textarea v-model="groupForm.description" class="input-field h-24 resize-none" placeholder="请输入描述"></textarea>
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">初始成员</label>
              <a-select
                v-model:value="groupForm.initial_member_ids"
                mode="multiple"
                style="width: 100%"
                placeholder="搜索并选择用户"
                :options="allUsers.map(u => ({
                  label: `${u.username} (${u.full_name || u.email})`,
                  value: u.id,
                }))"
                :max-tag-count="3"
                :max-tag-text-length="20"
                show-search
                :filter-option="(input: string, option: any) => option.label.toLowerCase().includes(input.toLowerCase())"
              />
            </div>
            <div class="flex justify-end gap-2 pt-4">
              <button type="button" @click="showModal = false" class="btn-secondary">取消</button>
              <button type="submit" :disabled="modalLoading" class="btn-primary">
                {{ modalLoading ? '处理中...' : '创建' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Edit Group Modal -->
    <div v-if="showEditModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showEditModal = false"></div>
      <div class="relative bg-white w-full max-w-md rounded-xl shadow-2xl">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">编辑用户组</h2>
          <button @click="showEditModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleEditSubmit" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">用户组名称 <span class="text-red-500">*</span></label>
              <input v-model="groupForm.name" type="text" class="input-field" placeholder="请输入用户组名称" />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">用户组描述</label>
              <textarea v-model="groupForm.description" class="input-field h-24 resize-none" placeholder="请输入描述"></textarea>
            </div>
            <div class="flex justify-end gap-2 pt-4">
              <button type="button" @click="showEditModal = false" class="btn-secondary">取消</button>
              <button type="submit" :disabled="modalLoading" class="btn-primary">
                {{ modalLoading ? '处理中...' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Authorizations Modal -->
    <div v-if="showAuthModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showAuthModal = false"></div>
      <div class="relative bg-white w-full max-w-3xl rounded-xl shadow-2xl max-h-[80vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">已授权资产 - {{ selectedGroup?.name }}</h2>
          <button @click="showAuthModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <div v-if="authLoading" class="text-center py-8 text-slate-500">加载中...</div>
          <div v-else-if="groupAuthorizations.length === 0" class="text-center py-8 text-slate-500">暂无授权记录</div>
          <table v-else class="data-table">
            <thead>
              <tr>
                <th>资产名称</th>
                <th>资产类型</th>
                <th>权限</th>
                <th>有效期</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="auth in groupAuthorizations" :key="auth.id">
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
                  <span class="text-sm text-slate-600">{{ auth.valid_until ? formatDate(auth.valid_until) : '永久' }}</span>
                </td>
                <td>
                  <span class="badge badge-success">
                    <span class="inline-block w-1.5 h-1.5 rounded-full mr-1 bg-success"></span>
                    {{ auth.status === 'active' ? '启用' : '禁用' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="flex justify-end mt-4">
            <button @click="showAuthModal = false" class="btn-secondary">关闭</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Members Modal -->
    <div v-if="showMembersModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showMembersModal = false"></div>
      <div class="relative bg-white w-full max-w-2xl rounded-xl shadow-2xl max-h-[80vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">管理成员 - {{ selectedGroup?.name }}</h2>
          <button @click="showMembersModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <!-- Add Members -->
          <div class="bg-slate-50 rounded-lg p-4 mb-4">
            <h4 class="font-medium text-slate-700 mb-3">添加成员</h4>
            <div class="flex gap-2">
              <a-select
                v-model:value="selectedUserIds"
                mode="multiple"
                style="width: 100%"
                placeholder="搜索并选择用户"
                :options="allUsers.filter(u => !isMember(u.id)).map(u => ({
                  label: `${u.username} (${u.full_name || u.email})`,
                  value: u.id,
                }))"
                :max-tag-count="3"
                :max-tag-text-length="20"
                show-search
                :filter-option="(input: string, option: any) => option.label.toLowerCase().includes(input.toLowerCase())"
              />
              <button @click="handleAddMembers" class="btn-primary" :disabled="!selectedUserIds || selectedUserIds.length === 0" style="white-space: nowrap">
                <UserAddOutlined class="text-sm mr-1" />
                添加
              </button>
            </div>
          </div>

          <!-- Members List -->
          <h4 class="font-medium text-slate-700 mb-3">当前成员 ({{ groupMembers.length }})</h4>
          <div v-if="membersLoading" class="text-center py-4 text-slate-500">加载中...</div>
          <div v-else-if="groupMembers.length === 0" class="text-center py-4 text-slate-500">暂无成员</div>
          <div v-else class="space-y-2">
            <div
              v-for="member in groupMembers"
              :key="member.id"
              class="flex items-center justify-between bg-slate-50 rounded-lg p-3"
            >
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center">
                  <span class="text-primary font-medium text-sm">
                    {{ member.full_name?.[0] || member.username[0]?.toUpperCase() || 'U' }}
                  </span>
                </div>
                <div>
                  <p class="font-medium text-slate-900">{{ member.username }}</p>
                  <p class="text-xs text-slate-500">{{ member.full_name || member.email }}</p>
                </div>
              </div>
              <button
                @click="handleRemoveMember(member)"
                class="p-1.5 hover:bg-red-50 rounded text-slate-400 hover:text-red-600"
                title="移除"
              >
                <UserDeleteOutlined class="text-lg" />
              </button>
            </div>
          </div>

          <div class="flex justify-end mt-4">
            <button @click="showMembersModal = false" class="btn-secondary">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>