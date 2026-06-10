<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getPasswordLogs, type PasswordLog } from '@/api/logs'
import { formatDateTime } from '@/utils/datetime'

const router = useRouter()
const route = useRoute()

// Loading
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const limit = ref(20)

// Filters
const changeType = ref('')
const dateFrom = ref('')
const dateTo = ref('')

// Logs data
const logs = ref<PasswordLog[]>([])

// Change type labels
const changeTypeLabels: Record<string, string> = {
  'user_password': '用户密码',
  'asset_credential': '资产凭证'
}

// Fetch logs
async function fetchLogs() {
  loading.value = true
  try {
    const result = await getPasswordLogs({
      page: page.value,
      limit: limit.value,
      change_type: changeType.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined
    })
    logs.value = result.items
    total.value = result.total
  } catch (error) {
    console.error('Failed to fetch password logs')
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

// Handle page change
function handlePageChange(newPage: number) {
  page.value = newPage
  fetchLogs()
}

// Initial load
onMounted(() => {
  // Restore state from URL
  const query = route.query
  if (query.page) page.value = Number(query.page)
  if (query.type) changeType.value = query.type as string
  if (query.from) dateFrom.value = query.from as string
  if (query.to) dateTo.value = query.to as string

  fetchLogs()
})

// Sync state to URL
watch([page, changeType, dateFrom, dateTo], () => {
  const query: Record<string, string> = {}
  if (page.value !== 1) query.page = String(page.value)
  if (changeType.value) query.type = changeType.value
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
        <input type="date" v-model="dateFrom" class="input-field w-40" />
        <input type="date" v-model="dateTo" class="input-field w-40" />
        <select v-model="changeType" class="input-field w-32">
          <option value="">全部类型</option>
          <option value="user_password">用户密码</option>
          <option value="asset_credential">资产凭证</option>
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
            <th>类型</th>
            <th>操作者</th>
            <th>IP地址</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="text-center py-8 text-slate-500">加载中...</td>
          </tr>
          <tr v-else-if="logs.length === 0">
            <td colspan="5" class="text-center py-8 text-slate-500">暂无数据</td>
          </tr>
          <tr v-for="log in logs" :key="log.id">
            <td>
              <span class="text-sm text-slate-600 font-mono">{{ formatDateTime(log.created_at) }}</span>
            </td>
            <td>
              <div class="flex items-center gap-2">
                <div class="w-7 h-7 bg-primary/10 rounded-full flex items-center justify-center">
                  <span class="text-primary font-medium text-xs">{{ log.username?.[0] || '?' }}</span>
                </div>
                <span class="font-medium text-slate-900">{{ log.username }}</span>
              </div>
            </td>
            <td>
              <span class="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                {{ changeTypeLabels[log.change_type] || log.change_type }}
              </span>
            </td>
            <td>
              <span class="text-slate-600">{{ log.changed_by_name || '-' }}</span>
            </td>
            <td>
              <span class="text-sm text-slate-600 font-mono">{{ log.ip_address || '-' }}</span>
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
  </div>
</template>