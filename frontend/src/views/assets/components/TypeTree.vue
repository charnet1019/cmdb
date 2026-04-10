<script setup lang="ts">
import {
  DownOutlined,
  UpOutlined,
  RightOutlined,
  AppstoreOutlined
} from '@ant-design/icons-vue'

interface TypeNode {
  id: string
  name: string
  count: number
  level: number
  hasChildren: boolean
  isRoot?: boolean
  category?: string
  subCategory?: string
}

interface Props {
  flattenedTypeTree: TypeNode[]
  selectedTypeNodeId: string
  expandedTypeIds: string[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'toggleType', typeId: string): void
  (e: 'selectType', node: TypeNode): void
}>()

function isSelectedTypeNode(node: TypeNode): boolean {
  return props.selectedTypeNodeId === node.id
}

function getCategoryIcon(_category: string | undefined) {
  // Import icons dynamically or pass from parent
  return AppstoreOutlined
}
</script>

<template>
  <div class="text-sm">
    <template v-for="node in flattenedTypeTree" :key="node.id">
      <div
        class="py-1.5 px-2 rounded cursor-pointer hover:bg-slate-50 flex items-center gap-1"
        :class="isSelectedTypeNode(node) ? 'bg-primary/10 text-primary' : 'text-slate-600'"
        :style="{ paddingLeft: `${node.level * 16 + 8}px` }"
        @click="emit('selectType', node)"
      >
        <!-- Root node arrows -->
        <UpOutlined
          v-if="node.isRoot && expandedTypeIds.includes('all')"
          class="text-xs cursor-pointer hover:bg-slate-200 rounded"
          @click.stop="emit('toggleType', 'all')"
        />
        <DownOutlined
          v-if="node.isRoot && !expandedTypeIds.includes('all')"
          class="text-xs cursor-pointer hover:bg-slate-200 rounded"
          @click.stop="emit('toggleType', 'all')"
        />
        <!-- Level 1 node arrows -->
        <UpOutlined
          v-else-if="node.level === 1 && node.hasChildren && expandedTypeIds.includes(node.id)"
          class="text-xs cursor-pointer hover:bg-slate-200 rounded"
          @click.stop="emit('toggleType', node.id)"
        />
        <DownOutlined
          v-else-if="node.level === 1 && node.hasChildren && !expandedTypeIds.includes(node.id)"
          class="text-xs cursor-pointer hover:bg-slate-200 rounded"
          @click.stop="emit('toggleType', node.id)"
        />
        <!-- Level 2 arrow -->
        <RightOutlined v-else-if="node.level === 2" class="text-xs" />
        <!-- Spacer for leaf nodes -->
        <span v-else-if="node.level === 1 && !node.hasChildren" class="w-4"></span>

        <!-- Icon -->
        <AppstoreOutlined v-if="node.isRoot" class="text-sm mr-1" />
        <component v-else :is="getCategoryIcon(node.category)" class="text-sm mr-1" />

        <!-- Name -->
        <span class="flex-1 truncate">{{ node.name }}</span>
      </div>
    </template>
  </div>
</template>