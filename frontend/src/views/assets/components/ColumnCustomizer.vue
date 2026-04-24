<script setup lang="ts">
import { computed } from 'vue'
import { CloseOutlined } from '@ant-design/icons-vue'
import type { ColumnDefinition } from '../composables/useColumnConfig'

const props = defineProps<{
  visible: boolean
  columns: ColumnDefinition[]
  visibleKeys: Record<string, boolean>
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'toggle', key: string): void
  (e: 'reset'): void
}>()

const fixedColumns = computed(() =>
  props.columns.filter(col => col.fixed)
)

const toggleableColumns = computed(() =>
  props.columns.filter(col => !col.fixed)
)

const isAllSelected = computed(() =>
  toggleableColumns.value.length > 0 &&
  toggleableColumns.value.every(col => props.visibleKeys[col.key])
)

const isIndeterminate = computed(() => {
  const selected = toggleableColumns.value.filter(col => props.visibleKeys[col.key])
  return selected.length > 0 && selected.length < toggleableColumns.value.length
})

function toggleSelectAll() {
  const shouldSelectAll = !isAllSelected.value
  toggleableColumns.value.forEach(col => {
    const isCurrentlyVisible = props.visibleKeys[col.key]
    if (shouldSelectAll && !isCurrentlyVisible) {
      emit('toggle', col.key)
    } else if (!shouldSelectAll && isCurrentlyVisible) {
      emit('toggle', col.key)
    }
  })
}

function close() {
  emit('update:visible', false)
}
</script>

<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"></div>
    <div class="relative bg-white w-full max-w-lg rounded-xl shadow-2xl">
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
        <h2 class="text-lg font-bold text-slate-900">自定义列</h2>
        <button @click="close" class="p-1.5 hover:bg-slate-100 rounded-lg">
          <CloseOutlined class="text-slate-400" />
        </button>
      </div>
      <div class="p-6">
        <!-- 全选/取消全选 -->
        <div class="flex items-center gap-3 mb-4 pb-4 border-b border-slate-100">
          <input
            type="checkbox"
            :checked="isAllSelected"
            :indeterminate="isIndeterminate"
            @change="toggleSelectAll"
            class="rounded border-gray-300 w-4 h-4"
          />
          <span class="text-sm font-medium text-slate-700">全选</span>
        </div>

        <!-- 固定列 (始终显示) -->
        <div class="mb-4 pb-4 border-b border-slate-100">
          <div class="text-xs text-slate-400 mb-3">固定显示</div>
          <div class="grid grid-cols-3 gap-3">
            <div
              v-for="col in fixedColumns"
              :key="col.key"
              class="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg"
            >
              <input
                type="checkbox"
                checked
                disabled
                class="rounded border-gray-300 w-4 h-4 cursor-not-allowed"
              />
              <span class="text-sm text-slate-500">{{ col.label }}</span>
            </div>
          </div>
        </div>

        <!-- 可切换列 -->
        <div class="grid grid-cols-3 gap-3">
          <div
            v-for="col in toggleableColumns"
            :key="col.key"
            class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
          >
            <input
              :id="`col-${col.key}`"
              type="checkbox"
              :checked="visibleKeys[col.key]"
              class="rounded border-gray-300 w-4 h-4"
              @change="emit('toggle', col.key)"
            />
            <label :for="`col-${col.key}`" class="text-sm text-slate-700 cursor-pointer select-none">{{ col.label }}</label>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-100">
          <button
            @click="emit('reset')"
            class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg"
          >
            重置
          </button>
          <button
            @click="close"
            class="btn-primary"
          >
            确定
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
