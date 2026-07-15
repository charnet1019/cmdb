<script setup lang="ts">
defineProps<{
  total: number
  page: number
  limit: number
  getPageNumbers: (total: number) => (number | string)[]
}>()

const emit = defineEmits<{
  limitChange: [value: number]
  pageChange: [page: number]
}>()

function onLimitChange(event: Event) {
  const value = Number((event.target as HTMLSelectElement).value)
  emit('limitChange', value)
}
</script>

<template>
  <div class="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
    <span class="text-sm text-slate-500">共 {{ total }} 条记录</span>
    <div class="flex items-center gap-3">
      <select :value="limit" @change="onLimitChange" class="text-sm border border-slate-200 rounded px-2 py-1.5 bg-white focus:border-primary outline-none">
        <option :value="15">15条/页</option>
        <option :value="30">30条/页</option>
        <option :value="50">50条/页</option>
        <option :value="100">100条/页</option>
      </select>
      <div class="flex items-center gap-1">
        <button
          @click="emit('pageChange', page - 1)"
          :disabled="page === 1"
          class="px-2.5 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          上一页
        </button>
        <template v-for="(p, i) in getPageNumbers(total)" :key="i">
          <span v-if="p === '...'" class="px-2 py-1.5 text-sm text-slate-400">...</span>
          <button
            v-else
            @click="emit('pageChange', p as number)"
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
          @click="emit('pageChange', page + 1)"
          :disabled="page >= Math.ceil(total / limit)"
          class="px-2.5 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>
