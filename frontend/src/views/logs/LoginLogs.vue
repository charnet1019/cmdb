<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getLoginLogs, type LoginLog, type LoginLogStats } from '@/api/logs'
import { formatDateTime } from '@/utils/datetime'
import { useListPagination } from '@/composables/useListPagination'
import PaginationBar from '@/components/common/PaginationBar.vue'
import { SearchOutlined, CloseOutlined } from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()

// Stats
const stats = ref<LoginLogStats>({
  today_total: 0,
  success_rate: 0,
  failed_count: 0
})

// Loading
const loading = ref(false)
const total = ref(0)
const { page, limit, getPageNumbers, resetPage, handlePageChange, handleLimitChange } = useListPagination(fetchLogs)

// Filters
const searchQuery = ref('')
const statusFilter = ref('')
const dateFrom = ref('')
const dateTo = ref('')

// Logs data
const logs = ref<LoginLog[]>([])

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
    const result = await getLoginLogs({
      page: page.value,
      limit: limit.value,
      search: searchQuery.value || undefined,
      status: statusFilter.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined
    })
    logs.value = result.items
    total.value = result.total
    stats.value = result.stats
  } catch (error) {
    console.error('Failed to fetch login logs')
    logs.value = []
  } finally {
    loading.value = false
  }
}

// Handle search
function handleSearch() {
  resetPage()
  fetchLogs()
}

// Clear search
function clearSearch() {
  searchQuery.value = ''
  resetPage()
  fetchLogs()
}

// Initial load
onMounted(() => {
  // Restore state from URL
  const query = route.query
  if (query.page) page.value = Number(query.page)
  if (query.search) searchQuery.value = query.search as string
  if (query.status) statusFilter.value = query.status as string
  if (query.from) dateFrom.value = query.from as string
  if (query.to) dateTo.value = query.to as string

  fetchLogs()
})

// Sync state to URL
watch([page, searchQuery, statusFilter, dateFrom, dateTo], () => {
  const query: Record<string, string> = {}
  if (page.value !== 1) query.page = String(page.value)
  if (searchQuery.value) query.search = searchQuery.value
  if (statusFilter.value) query.status = statusFilter.value
  if (dateFrom.value) query.from = dateFrom.value
  if (dateTo.value) query.to = dateTo.value
  router.replace({ query })
}, { deep: true })
</script>

<template>
  <div class="space-y-4">
    <!-- Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="card">
        <p class="text-xs font-semibold text-slate-500 uppercase">今日总登录</p>
        <p class="text-3xl font-bold text-slate-900 mt-2 font-headline">{{ stats.today_total }}</p>
      </div>
      <div class="card">
        <p class="text-xs font-semibold text-slate-500 uppercase">成功率</p>
        <p class="text-3xl font-bold text-slate-900 mt-2 font-headline">{{ stats.success_rate }}%</p>
      </div>
      <div class="card">
        <p class="text-xs font-semibold text-slate-500 uppercase">失败次数</p>
        <p class="text-3xl font-bold text-red-600 mt-2 font-headline">{{ stats.failed_count }}</p>
      </div>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm p-4">
      <div class="flex items-center gap-4 flex-wrap">
        <div class="relative flex-1 min-w-[200px] max-w-md">
          <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索用户..."
            class="input-field pl-10 pr-8"
            @keyup.enter="handleSearch"
          />
          <button v-if="searchQuery" @click="clearSearch" class="absolute right-2 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors">
            <CloseOutlined class="text-sm" />
          </button>
        </div>
        <input type="date" v-model="dateFrom" class="input-field w-40" @click="openDatePicker" />
        <input type="date" v-model="dateTo" class="input-field w-40" @click="openDatePicker" />
        <select v-model="statusFilter" class="input-field w-28">
          <option value="">全部状态</option>
          <option value="success">成功</option>
          <option value="failed">失败</option>
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
            <th>用户</th>
            <th>来源IP</th>
            <th>状态</th>
            <th>失败原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="text-center py-8 text-slate-500">加载中...</td>
          </tr>
          <tr v-else-if="logs.length === 0">
            <td colspan="5" class="text-center py-8 text-slate-500">暂无数据</td>
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
              <span class="text-sm text-slate-600 font-mono">{{ log.ip_address }}</span>
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
              <span class="text-sm text-slate-500">{{ log.failure_reason }}</span>
            </td>
          </tr>
        </tbody>
      </table>

      <PaginationBar
        :total="total"
        :page="page"
        :limit="limit"
        :get-page-numbers="getPageNumbers"
        @page-change="handlePageChange"
        @limit-change="handleLimitChange"
      />
    </div>
  </div>
</template>