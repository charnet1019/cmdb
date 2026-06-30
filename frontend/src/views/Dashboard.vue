<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getDashboardStats } from '@/api/dashboard'
import type { DashboardStats } from '@/api/dashboard'
import {
  ClusterOutlined,
  TeamOutlined,
  WifiOutlined
} from '@ant-design/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

// Stats
const stats = ref<DashboardStats>({
  total_assets: 0,
  total_users: 0,
  active_users: 0,
  online_users: 0,
  asset_distribution: [],
  status_distribution: [],
  sub_distribution: {},
  recent_logins: []
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

// Status labels
const statusLabels: Record<string, string> = {
  inventory: '库存',
  deploying: '部署中',
  running: '运行中',
  maintenance: '维护中',
  deactivated: '停用',
  pending_scrap: '待报废',
  scrapped: '已报废',
  returned: '已退还'
}

// Status colors
const statusColors: Record<string, string> = {
  inventory: '#94a3b8',
  deploying: '#3b82f6',
  running: '#22c55e',
  maintenance: '#f59e0b',
  deactivated: '#ef4444',
  pending_scrap: '#f97316',
  scrapped: '#64748b',
  returned: '#a3e635'
}

// Stats labels
const statsLabels = ['资产总数', '用户总数', '在线用户']

// Stats icons mapping
const statsIconComponents = [ClusterOutlined, TeamOutlined, WifiOutlined]

// Whether the current user can view user stats (null means no permission)
const canViewUsers = computed(() => stats.value.total_users !== null && stats.value.total_users !== undefined)

// Main pie chart option
const mainPieOption = computed<EChartsOption>(() => {
  const data = stats.value.asset_distribution.map(item => ({
    name: assetLabels[item.type] || item.type,
    value: item.count,
    itemStyle: { color: assetColors[item.type] || '#6b7280' }
  }))
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: '#64748b', fontSize: 13 }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: true,
      label: {
        show: true,
        formatter: '{b}\n{c}',
        fontSize: 12,
        color: '#334155'
      },
      labelLine: { length: 15, length2: 10 },
      emphasis: {
        itemStyle: { shadowBlur: 8, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.15)' }
      },
      data: data.length ? data : [{ name: '-', value: 0, itemStyle: { color: '#e2e8f0' } }]
    }]
  }
})

// Status pie chart option
const statusPieOption = computed<EChartsOption>(() => {
  const data = stats.value.status_distribution.map(item => ({
    name: statusLabels[item.name] || item.name,
    value: item.count,
    itemStyle: { color: statusColors[item.name] || '#6b7280' }
  }))
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: '#64748b', fontSize: 13 }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: true,
      label: {
        show: true,
        formatter: '{b}\n{c}',
        fontSize: 12,
        color: '#334155'
      },
      labelLine: { length: 15, length2: 10 },
      emphasis: {
        itemStyle: { shadowBlur: 8, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.15)' }
      },
      data: data.length ? data : [{ name: '-', value: 0, itemStyle: { color: '#e2e8f0' } }]
    }]
  }
})

// Sub-pie chart options as computed map for reactivity
const subPieOptions = computed(() => {
  const result: Record<string, EChartsOption> = {}
  for (const category of Object.keys(stats.value.sub_distribution)) {
    const items = stats.value.sub_distribution[category]
    if (!items.length) continue
    const baseColor = assetColors[category] || '#6b7280'
    const palette = generatePalette(baseColor)

    const data = items.map((item, i) => ({
      name: item.name,
      value: item.count,
      itemStyle: { color: palette[i % palette.length] }
    }))

    result[category] = {
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)'
      },
      series: [{
        type: 'pie',
        radius: ['45%', '75%'],
        label: {
          show: true,
          formatter: '{b}\n{c}',
          fontSize: 11,
          color: '#334155'
        },
        labelLine: { length: 10, length2: 8 },
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.15)' }
        },
        data: data.length ? data : [{ name: '-', value: 0, itemStyle: { color: '#e2e8f0' } }]
      }]
    }
  }
  return result
})

// Generate distinct colors by rotating hue from base color
function generatePalette(baseColor: string, count: number = 10): string[] {
  const hex = baseColor.replace('#', '')
  const r = parseInt(hex.substring(0, 2), 16) / 255
  const g = parseInt(hex.substring(2, 4), 16) / 255
  const b = parseInt(hex.substring(4, 6), 16) / 255
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  let h = 0, s = 0, l = (max + min) / 2
  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
    else if (max === g) h = ((b - r) / d + 2) / 6
    else h = ((r - g) / d + 4) / 6
  }
  const colors: string[] = []
  const hueStep = 360 / count
  for (let i = 0; i < count; i++) {
    const newH = ((h * 360 + i * hueStep) % 360) / 360
    colors.push(hslToHex(newH, s, l))
  }
  return colors
}

function hslToHex(h: number, s: number, l: number): string {
  const k = (n: number) => (n + h * 12) % 12
  const a = s * Math.min(l, 1 - l)
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))
  const toHex = (v: number) => Math.round(v * 255).toString(16).padStart(2, '0')
  return `#${toHex(f(0))}${toHex(f(8))}${toHex(f(4))}`
}

// Categories that have sub-distribution data (non-zero)
const categoriesWithSubs = computed(() => {
  return Object.entries(stats.value.sub_distribution)
    .filter(([_, items]) => items.length > 0)
    .map(([category]) => category)
})

// Fetch dashboard data
async function fetchDashboardData() {
  loading.value = true
  try {
    const statsData = await getDashboardStats()
    stats.value = statsData
  } catch (error) {
    console.error('Failed to fetch dashboard data', error)
  } finally {
    loading.value = false
  }
}

// Initial load
onMounted(() => {
  fetchDashboardData()
})
</script>

<template>
  <div class="space-y-4">
    <!-- Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6" v-if="canViewUsers">
      <div
        v-for="stat in [
          { label: statsLabels[0], value: stats.total_assets, icon: statsIconComponents[0] },
          { label: statsLabels[1], value: stats.total_users, icon: statsIconComponents[1] },
          { label: statsLabels[2], value: stats.online_users, icon: statsIconComponents[2] }
        ]"
        :key="stat.label"
        class="card"
      >
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">{{ stat.label }}</p>
            <p class="text-3xl font-bold text-slate-900 mt-2 font-headline">{{ stat.value!.toLocaleString() }}</p>
          </div>
          <div class="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-primary-container flex items-center justify-center">
            <component :is="stat.icon" class="text-white" />
          </div>
        </div>
      </div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6" v-else>
      <div class="card">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">{{ statsLabels[0] }}</p>
            <p class="text-3xl font-bold text-slate-900 mt-2 font-headline">{{ stats.total_assets.toLocaleString() }}</p>
          </div>
          <div class="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-primary-container flex items-center justify-center">
            <component :is="statsIconComponents[0]" class="text-white" />
          </div>
        </div>
      </div>
    </div>

    <!-- Asset Type Distribution + Status Distribution -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="card">
        <h3 class="text-lg font-semibold text-slate-900 mb-4">资产类型分布</h3>
        <v-chart class="h-80" :option="mainPieOption" autoresize />
      </div>
      <div class="card">
        <h3 class="text-lg font-semibold text-slate-900 mb-4">资产状态分布</h3>
        <v-chart class="h-80" :option="statusPieOption" autoresize />
      </div>
    </div>

    <!-- Sub-category Pie Charts -->
    <div v-if="categoriesWithSubs.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="category in categoriesWithSubs"
        :key="category"
        class="card"
      >
        <h4 class="text-sm font-semibold text-slate-900 mb-2">{{ assetLabels[category] || category }} - 细分</h4>
        <v-chart class="h-56" :option="subPieOptions[category]" autoresize />
      </div>
    </div>

    <!-- Recent Logins -->
    <div class="card" v-if="canViewUsers && stats.recent_logins && stats.recent_logins.length > 0">
      <h3 class="text-lg font-semibold text-slate-900 mb-4">最近登录用户</h3>
      <div class="space-y-3">
        <div
          v-for="login in stats.recent_logins"
          :key="login.user_id + login.time"
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
            <span
              v-if="login.is_online"
              class="inline-flex items-center gap-1 text-xs text-success"
            >
              <span class="w-1.5 h-1.5 bg-success rounded-full"></span>
              在线
            </span>
            <span
              v-else
              class="inline-flex items-center gap-1 text-xs text-slate-400"
            >
              <span class="w-1.5 h-1.5 bg-slate-300 rounded-full"></span>
              离线
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
