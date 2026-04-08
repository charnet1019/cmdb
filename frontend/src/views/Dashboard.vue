<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getDashboardStats, getDashboardAlerts } from '@/api/dashboard'
import type { DashboardStats, DashboardAlerts } from '@/api/dashboard'
import {
  ClusterOutlined,
  TeamOutlined,
  WifiOutlined,
  WarningOutlined,
  PlusCircleOutlined,
  UserAddOutlined,
  KeyOutlined,
  HistoryOutlined
} from '@ant-design/icons-vue'

// Stats
const stats = ref<DashboardStats>({
  total_assets: 0,
  active_assets: 0,
  total_users: 0,
  active_users: 0,
  online_users: 0,
  asset_distribution: [],
  recent_logins: []
})

const alerts = ref<DashboardAlerts>({
  alerts: 0,
  failed_logins_24h: 0
})

const loading = ref(false)

// Asset type colors
const assetColors: Record<string, string> = {
  host: '#005daa',
  network: '#0075d5',
  database: '#22c55e',
  cloud: '#f59e0b',
  web: '#8b5cf6',
  gpt: '#ec4899'
}

// Asset type labels
const assetLabels: Record<string, string> = {
  host: '主机',
  network: '网络设备',
  database: '数据库',
  cloud: '云服务',
  web: '网站服务',
  gpt: 'AI服务'
}

// Stats labels
const statsLabels = ['资产总数', '用户总数', '在线用户', '告警数量']

// Stats icons mapping
const statsIconComponents = [ClusterOutlined, TeamOutlined, WifiOutlined, WarningOutlined]

// Fetch dashboard data
async function fetchDashboardData() {
  loading.value = true
  try {
    const [statsData, alertsData] = await Promise.all([
      getDashboardStats(),
      getDashboardAlerts()
    ])
    stats.value = statsData
    alerts.value = alertsData
  } catch (error) {
    console.error('Failed to fetch dashboard data', error)
  } finally {
    loading.value = false
  }
}

// Get asset distribution with colors
function getAssetDistribution() {
  return stats.value.asset_distribution.map((item: { type: string; count: number }) => ({
    type: assetLabels[item.type] || item.type,
    count: item.count,
    color: assetColors[item.type] || '#6b7280'
  }))
}

// Initial load
onMounted(() => {
  fetchDashboardData()
})
</script>

<template>
  <div class="space-y-4">
    <!-- Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div
        v-for="stat in [
          { label: statsLabels[0], value: stats.total_assets, icon: statsIconComponents[0] },
          { label: statsLabels[1], value: stats.total_users, icon: statsIconComponents[1] },
          { label: statsLabels[2], value: stats.online_users, icon: statsIconComponents[2] },
          { label: statsLabels[3], value: alerts.alerts, icon: statsIconComponents[3] }
        ]"
        :key="stat.label"
        class="card"
      >
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">{{ stat.label }}</p>
            <p class="text-3xl font-bold text-slate-900 mt-2 font-headline">{{ stat.value.toLocaleString() }}</p>
          </div>
          <div class="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-primary-container flex items-center justify-center">
            <component :is="stat.icon" class="text-white" />
          </div>
        </div>
      </div>
    </div>

    <!-- Charts Section -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Asset Type Distribution -->
      <div class="card">
        <h3 class="text-lg font-semibold text-slate-900 mb-4">资产类型分布</h3>
        <div class="space-y-4">
          <div
            v-for="item in getAssetDistribution()"
            :key="item.type"
            class="flex items-center gap-4"
          >
            <div class="w-3 h-3 rounded-full" :style="{ backgroundColor: item.color }"></div>
            <span class="flex-1 text-sm text-slate-600">{{ item.type }}</span>
            <span class="text-sm font-medium text-slate-900">{{ item.count }}</span>
            <div class="w-24 h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                class="h-full rounded-full"
                :style="{
                  width: `${(item.count / stats.total_assets) * 100}%`,
                  backgroundColor: item.color
                }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent Logins -->
      <div class="card">
        <h3 class="text-lg font-semibold text-slate-900 mb-4">最近登录用户</h3>
        <div class="space-y-3">
          <div
            v-for="login in stats.recent_logins"
            :key="login.user + login.time"
            class="flex items-center gap-3 p-3 bg-surface-container-low rounded-lg"
          >
            <div class="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center">
              <span class="text-primary font-medium">{{ login.user[0] }}</span>
            </div>
            <div class="flex-1">
              <p class="text-sm font-medium text-slate-900">{{ login.user }}</p>
              <p class="text-xs text-slate-500">{{ login.ip }}</p>
            </div>
            <div class="text-right">
              <p class="text-sm text-slate-600">{{ login.time }}</p>
              <span class="inline-flex items-center gap-1 text-xs text-success">
                <span class="w-1.5 h-1.5 bg-success rounded-full"></span>
                在线
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="card">
      <h3 class="text-lg font-semibold text-slate-900 mb-4">快捷操作</h3>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <router-link
          v-for="action in [
            { icon: PlusCircleOutlined, label: '添加资产', path: '/assets' },
            { icon: UserAddOutlined, label: '创建用户', path: '/users' },
            { icon: KeyOutlined, label: '资产授权', path: '/permissions/authorizations' },
            { icon: HistoryOutlined, label: '操作日志', path: '/logs/operation' }
          ]"
          :key="action.label"
          :to="action.path"
          class="flex flex-col items-center gap-2 p-4 bg-surface-container-low rounded-xl hover:bg-surface-container-high transition-colors"
        >
          <component :is="action.icon" class="text-2xl text-primary" />
          <span class="text-sm text-slate-700">{{ action.label }}</span>
        </router-link>
      </div>
    </div>
  </div>
</template>