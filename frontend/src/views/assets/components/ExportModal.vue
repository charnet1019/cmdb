<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { CloseOutlined } from '@ant-design/icons-vue'
import { exportAssets } from '@/api/assets'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  visible: boolean
  category: string
  selectedIds: string[]
  searchQuery: string
  organizationId: number | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

// Export configuration
const exportFormat = ref<'excel' | 'csv'>('excel')
const exportScope = ref<'all' | 'selected' | 'filtered'>('all')
const exporting = ref(false)
const authStore = useAuthStore()

// Reset state when modal opens
function resetState() {
  exportFormat.value = 'excel'
  exportScope.value = 'all'
  exporting.value = false
}

// Watch visibility to reset state
watch(() => props.visible, (visible) => {
  if (visible) {
    resetState()
  }
})

// Execute export
async function handleExport() {
  // Validate selected scope when no items selected
  if (exportScope.value === 'selected' && props.selectedIds.length === 0) {
    message.warning('请选择要导出的资产')
    return
  }

  exporting.value = true
  try {
    await exportAssets({
      format: exportFormat.value,
      scope: exportScope.value,
      category: props.category !== 'all' ? props.category : undefined,
      organization_id: props.organizationId || undefined,
      search: props.searchQuery || undefined,
      ids: exportScope.value === 'selected' ? props.selectedIds.join(',') : undefined,
      include_passwords: authStore.hasPermission('export_pwd')
    })
    message.success('导出成功')
    emit('update:visible', false)
  } catch (error: any) {
    message.error(error.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

// Close modal
function close() {
  emit('update:visible', false)
}

// Scope labels
const scopeLabels = {
  all: '导出所有',
  selected: '仅导出选择项',
  filtered: '仅导出搜索结果'
}
</script>

<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="close"></div>
    <div class="relative bg-white w-full max-w-md rounded-xl shadow-2xl">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
        <h2 class="text-lg font-bold text-slate-900">导出</h2>
        <button @click="close" class="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
          <CloseOutlined class="text-slate-400" />
        </button>
      </div>

      <!-- Content -->
      <div class="p-6 space-y-6">
        <!-- Row 1: File type -->
        <div class="flex items-center gap-6">
          <span class="text-sm font-medium text-slate-700">文件类型</span>
          <div class="flex items-center gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                v-model="exportFormat"
                value="excel"
                class="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
              />
              <span class="text-sm text-slate-600">Excel</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                v-model="exportFormat"
                value="csv"
                class="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
              />
              <span class="text-sm text-slate-600">CSV</span>
            </label>
          </div>
        </div>

        <!-- Row 2: Export scope -->
        <div>
          <span class="text-sm font-medium text-slate-700">导出范围</span>
          <div class="mt-2 space-y-2">
            <label class="flex items-center gap-3 cursor-pointer p-2 hover:bg-slate-50 rounded-lg transition-colors">
              <input
                type="radio"
                v-model="exportScope"
                value="all"
                class="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
              />
              <span class="text-sm text-slate-600">{{ scopeLabels.all }}</span>
            </label>
            <label class="flex items-center gap-3 cursor-pointer p-2 hover:bg-slate-50 rounded-lg transition-colors" :class="{ 'opacity-50 cursor-not-allowed': props.selectedIds.length === 0 }">
              <input
                type="radio"
                v-model="exportScope"
                value="selected"
                :disabled="props.selectedIds.length === 0"
                class="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
              />
              <span class="text-sm text-slate-600">{{ scopeLabels.selected }}</span>
              <span v-if="props.selectedIds.length > 0" class="text-xs text-slate-400 ml-auto">({{ props.selectedIds.length }} 项)</span>
              <span v-else class="text-xs text-slate-400 ml-auto">(请先选择资产)</span>
            </label>
            <label class="flex items-center gap-3 cursor-pointer p-2 hover:bg-slate-50 rounded-lg transition-colors" :class="{ 'opacity-50 cursor-not-allowed': !props.searchQuery }">
              <input
                type="radio"
                v-model="exportScope"
                value="filtered"
                class="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
                :disabled="!props.searchQuery"
              />
              <span class="text-sm text-slate-600">{{ scopeLabels.filtered }}</span>
              <span v-if="props.searchQuery" class="text-xs text-slate-400 ml-auto">"{{ props.searchQuery }}"</span>
              <span v-if="!props.searchQuery" class="text-xs text-slate-400 ml-auto">(无搜索条件)</span>
            </label>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="flex justify-end gap-3 pt-4 border-t border-slate-100">
          <button
            @click="close"
            class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
          >
            取消
          </button>
          <button
            @click="handleExport"
            :disabled="exporting"
            class="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ exporting ? '导出中...' : '导出' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>