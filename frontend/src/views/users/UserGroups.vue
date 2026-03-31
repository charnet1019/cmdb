<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getGroups, createGroup, deleteGroup } from '@/api/users'
import type { Group } from '@/types'

// Data
const groups = ref<Group[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const limit = ref(20)

// Filters
const searchQuery = ref('')

// Modal states
const showModal = ref(false)
const modalLoading = ref(false)

// Form state
const groupForm = ref({
  name: '',
  description: ''
})

// Fetch groups
async function fetchGroups() {
  loading.value = true
  try {
    const result = await getGroups({
      page: page.value,
      limit: limit.value,
      search: searchQuery.value || undefined
    })
    groups.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    message.error('获取用户组列表失败')
    groups.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// Handle search
function handleSearch() {
  page.value = 1
  fetchGroups()
}

// Open create modal
function openCreateModal() {
  groupForm.value = {
    name: '',
    description: ''
  }
  showModal.value = true
}

// Submit group form
async function handleSubmit() {
  if (!groupForm.value.name) {
    message.error('请输入用户组名称')
    return
  }

  modalLoading.value = true
  try {
    await createGroup({
      name: groupForm.value.name,
      description: groupForm.value.description
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

// Delete group
async function handleDelete(group: Group) {
  if (!confirm(`确定要删除用户组 "${group.name}" 吗?`)) return

  try {
    await deleteGroup(group.id)
    message.success('用户组已删除')
    fetchGroups()
  } catch (error) {
    message.error('删除失败')
  }
}

// Format date
function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

// Initial load
onMounted(() => {
  fetchGroups()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">用户组</h1>
        <p class="text-slate-500 mt-1">管理用户组及其所属权限</p>
      </div>
      <button @click="openCreateModal" class="btn-primary flex items-center gap-2">
        <span class="material-symbols-outlined">group_add</span>
        创建用户组
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
                  <span class="material-symbols-outlined text-primary">shield</span>
                </div>
                <span class="font-medium text-slate-900">{{ group.name }}</span>
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
                <button class="text-xs text-primary hover:underline flex items-center gap-1">
                  <span class="material-symbols-outlined text-sm">shield</span>
                  已授权资产
                </button>
                <button @click="handleDelete(group)" class="p-1.5 hover:bg-red-50 rounded text-slate-400 hover:text-red-600" title="删除">
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
            @click="page--; fetchGroups()"
            :disabled="page === 1"
            class="px-3 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50"
          >
            上一页
          </button>
          <span class="text-sm text-slate-600">{{ page }} / {{ Math.ceil(total / limit) || 1 }}</span>
          <button
            @click="page++; fetchGroups()"
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
            <span class="material-symbols-outlined">close</span>
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
  </div>
</template>