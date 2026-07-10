<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getOperationLogs } from '@/api/logs'
import { formatDateTime } from '@/utils/datetime'
import { SearchOutlined, CloseOutlined } from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()

// Loading
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const limit = ref(15)

// Filters
const searchQuery = ref('')
const actionFilter = ref('')
const dateFrom = ref('')
const dateTo = ref('')

// Logs data
const logs = ref<any[]>([])

// Action colors
const actionColors: Record<string, string> = {
  'create': 'bg-green-100 text-green-700',
  'update': 'bg-blue-100 text-blue-700',
  'delete': 'bg-red-100 text-red-700',
  'authorize': 'bg-yellow-100 text-yellow-700',
  'download': 'bg-cyan-100 text-cyan-700',
  'import': 'bg-purple-100 text-purple-700',
  'export': 'bg-indigo-100 text-indigo-700'
}

// Action labels
const actionLabels: Record<string, string> = {
  'create': '创建',
  'update': '更新',
  'delete': '删除',
  'authorize': '授权',
  'download': '下载',
  'import': '导入',
  'export': '导出'
}

// Force open date picker on click
function openDatePicker(e: MouseEvent) {
  const target = e.target as HTMLInputElement
  if (target.showPicker) {
    target.showPicker()
  }
}

// Fetch logs
async function fetchLogs() {
  loading.value = true
  try {
    const result = await getOperationLogs({
      page: page.value,
      limit: limit.value,
      search: searchQuery.value || undefined,
      action: actionFilter.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined
    })
    logs.value = result.items
    total.value = result.total
  } catch (error) {
    console.error('Failed to fetch operation logs')
    logs.value = []
  } finally {
    loading.value = false
  }
}

// Handle search
function handleSearch() {
  page.value = 1
  fetchLogs()
}

// Clear search
function clearSearch() {
  searchQuery.value = ''
  page.value = 1
  fetchLogs()
}

// Handle page change
function handlePageChange(newPage: number) {
  page.value = newPage
  fetchLogs()
}

// Handle limit change
function handleLimitChange() {
  page.value = 1
  fetchLogs()
}

// Get visible page numbers for pagination
function getPageNumbers(): (number | string)[] {
  const totalPages = Math.ceil(total.value / limit.value) || 1
  const pages: (number | string)[] = []

  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i)
    }
  } else {
    pages.push(1)
    if (page.value > 3) pages.push('...')
    const start = Math.max(2, page.value - 1)
    const end = Math.min(totalPages - 1, page.value + 1)
    for (let i = start; i <= end; i++) {
      pages.push(i)
    }
    if (page.value < totalPages - 2) pages.push('...')
    pages.push(totalPages)
  }

  return pages
}

// Get action label
function getActionLabel(action: string): string {
  return actionLabels[action] || action
}

// Initial load
onMounted(() => {
  // Restore state from URL
  const query = route.query
  if (query.page) page.value = Number(query.page)
  if (query.search) searchQuery.value = query.search as string
  if (query.action) actionFilter.value = query.action as string
  if (query.from) dateFrom.value = query.from as string
  if (query.to) dateTo.value = query.to as string

  fetchLogs()
})

// Sync state to URL
watch([page, searchQuery, actionFilter, dateFrom, dateTo], () => {
  const query: Record<string, string> = {}
  if (page.value !== 1) query.page = String(page.value)
  if (searchQuery.value) query.search = searchQuery.value
  if (actionFilter.value) query.action = actionFilter.value
  if (dateFrom.value) query.from = dateFrom.value
  if (dateTo.value) query.to = dateTo.value
  router.replace({ query })
}, { deep: true })
</script>

<template>
  <div class="space-y-4">
    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-4 flex-wrap">
        <div class="relative flex-1 min-w-[200px] max-w-md">
          <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索..."
            class="input-field pl-10 pr-8"
            @keyup.enter="handleSearch"
          />
          <button v-if="searchQuery" @click="clearSearch" class="absolute right-2 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors">
            <CloseOutlined class="text-sm" />
          </button>
        </div>
        <input type="date" v-model="dateFrom" class="input-field w-40" @click="openDatePicker" />
        <input type="date" v-model="dateTo" class="input-field w-40" @click="openDatePicker" />
        <select v-model="actionFilter" class="input-field w-32" @change="handleSearch">
          <option value="">操作类型</option>
          <option value="create">创建</option>
          <option value="update">更新</option>
          <option value="delete">删除</option>
          <option value="authorize">授权</option>
          <option value="download">下载</option>
          <option value="import">导入</option>
          <option value="export">导出</option>
        </select>
        <button @click="handleSearch" class="btn-secondary">筛选</button>
      </div>
    </div>

    <!-- Logs Table -->
    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <table class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>操作者</th>
            <th>操作类型</th>
            <th>资源类型</th>
            <th>资源名称</th>
            <th>状态</th>
            <th>IP</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7" class="text-center py-8 text-slate-500">加载中...</td>
          </tr>
          <tr v-else-if="logs.length === 0">
            <td colspan="7" class="text-center py-8 text-slate-500">暂无数据</td>
          </tr>
          <tr v-for="log in logs" :key="log.id" :class="log.status === 'failed' ? 'bg-red-50/50' : ''">
            <td>
              <span class="text-sm text-slate-600 font-mono">{{ formatDateTime(log.created_at) }}</span>
            </td>
            <td>
              <div class="flex items-center gap-2">
                <div class="w-7 h-7 bg-primary/10 rounded-full flex items-center justify-center">
                  <span class="text-primary font-medium text-xs">{{ log.username?.[0] }}</span>
                </div>
                <span class="font-medium text-slate-900">{{ log.username }}</span>
              </div>
            </td>
            <td>
              <span class="px-2 py-0.5 rounded text-xs font-bold uppercase" :class="actionColors[log.action] || 'bg-slate-100 text-slate-700'">
                {{ getActionLabel(log.action) }}
              </span>
            </td>
            <td>
              <span class="text-sm text-slate-600">{{ log.resource_type }}</span>
            </td>
            <td>
              <span class="text-sm text-slate-600">{{ log.resource_name }}</span>
            </td>
            <td>
              <span v-if="log.status === 'success'" class="badge badge-success">
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-success mr-1"></span>
                成功
              </span>
              <span v-else class="badge badge-error">
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-error mr-1"></span>
                失败
              </span>
            </td>
            <td>
              <span class="text-sm text-slate-600 font-mono">{{ log.ip_address }}</span>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div class="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
        <span class="text-sm text-slate-500">共 {{ total }} 条记录</span>
        <div class="flex items-center gap-3">
          <select v-model.number="limit" @change="handleLimitChange" class="text-sm border border-slate-200 rounded px-2 py-1.5 bg-white focus:border-primary outline-none">
            <option :value="15">15条/页</option>
            <option :value="30">30条/页</option>
            <option :value="50">50条/页</option>
            <option :value="100">100条/页</option>
          </select>
          <div class="flex items-center gap-1">
            <button
              @click="handlePageChange(page - 1)"
              :disabled="page === 1"
              class="px-2.5 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              上一页
            </button>
            <template v-for="(p, i) in getPageNumbers()" :key="i">
              <span v-if="p === '...'" class="px-2 py-1.5 text-sm text-slate-400">...</span>
              <button
                v-else
                @click="handlePageChange(p as number)"
                :class="[
                  'px-2.5 py-1.5 text-sm border rounded transition-colors',
                  page === p
                    ? 'bg-primary text-white border-primary'
                    : 'border-slate-200 hover:bg-slate-50'
                ]"
              >
                {{ p }}
              </button>
            </template>
            <button
              @click="handlePageChange(page + 1)"
              :disabled="page >= Math.ceil(total / limit)"
              class="px-2.5 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              下一页
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>