<script setup lang="ts">
import {
  FolderOpenOutlined,
  FolderOutlined,
  FileTextOutlined,
  DownOutlined,
  RightOutlined,
  FolderAddOutlined,
  EditOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'

interface FlattenedOrg {
  id: number
  name: string
  count: number
  level: number
  hasChildren: boolean
}

interface Props {
  flattenedOrgs: FlattenedOrg[]
  selectedOrgId: number | null
  isRootExpanded: boolean
  totalAssetCount: number
  draggedOrgId: number | null
  dragOverOrgId: number | null
  showOrgContextMenu: boolean
  orgContextMenuPosition: { x: number; y: number }
  orgContextMenuTarget: { id: number | null; name: string; isRoot: boolean } | null
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'toggleRootExpansion'): void
  (e: 'toggleOrg', orgId: number): void
  (e: 'selectOrganization', orgId: number | null): void
  (e: 'handleOrgContextMenu', event: MouseEvent, org: { id: number | null; name: string; isRoot: boolean }): void
  (e: 'handleOrgDragStart', event: DragEvent, orgId: number): void
  (e: 'handleOrgDragOver', event: DragEvent, orgId: number | null): void
  (e: 'handleOrgDragLeave'): void
  (e: 'handleOrgDrop', event: DragEvent, orgId: number | null): void
  (e: 'handleOrgDragEnd'): void
  (e: 'openCreateOrgModal', parentId: number | null): void
  (e: 'openRenameOrgModal', org: { id: number | null; name: string; isRoot: boolean } | null): void
  (e: 'handleDeleteOrg', org: { id: number | null; name: string; isRoot: boolean } | null): void
}>()

function isOrgExpanded(_orgId: number): boolean {
  // This should be passed from parent or use a Set
  return true // Simplified, actual implementation needs expandedOrgIds Set
}

function handleRootClick() {
  emit('toggleRootExpansion')
}

function handleOrgClick(org: FlattenedOrg) {
  if (org.hasChildren) {
    emit('toggleOrg', org.id)
  } else {
    emit('selectOrganization', org.id)
  }
}
</script>

<template>
  <div class="text-sm">
    <!-- Root Node -->
    <div
      class="py-2 px-2 rounded cursor-pointer hover:bg-slate-50 mb-1 font-medium"
      :class="[
        selectedOrgId === null && isRootExpanded ? 'bg-primary/10 text-primary' : 'text-slate-700',
        dragOverOrgId === null && draggedOrgId !== null ? 'bg-blue-50' : ''
      ]"
      @click="handleRootClick"
      @contextmenu.prevent.stop="emit('handleOrgContextMenu', $event, { id: null, name: 'Default', isRoot: true })"
      @dragover.prevent="emit('handleOrgDragOver', $event, null)"
      @dragleave="emit('handleOrgDragLeave')"
      @drop.prevent="emit('handleOrgDrop', $event, null)"
    >
      <div class="flex items-center gap-1">
        <DownOutlined v-if="isRootExpanded" class="text-xs cursor-pointer hover:bg-slate-200 rounded p-0.5" />
        <RightOutlined v-else class="text-xs cursor-pointer hover:bg-slate-200 rounded p-0.5" />
        <FolderOpenOutlined v-if="isRootExpanded" class="text-sm" />
        <FolderOutlined v-else class="text-sm" />
        <span class="flex-1">Default</span>
        <span class="text-xs text-slate-400">({{ totalAssetCount }})</span>
      </div>
    </div>

    <!-- Child Nodes -->
    <template v-if="isRootExpanded">
      <div
        v-for="org in flattenedOrgs"
        :key="org.id"
        class="py-1.5 px-2 rounded cursor-pointer hover:bg-slate-50 flex items-center gap-1"
        :class="{
          'bg-primary/10 text-primary': selectedOrgId === org.id,
          'text-slate-600': selectedOrgId !== org.id,
          'opacity-50': draggedOrgId === org.id,
          'bg-blue-50 border-t-2 border-primary': dragOverOrgId === org.id
        }"
        :style="{ paddingLeft: `${(org.level + 1) * 20 + 8}px` }"
        @click.stop="handleOrgClick(org)"
        @contextmenu.prevent.stop="emit('handleOrgContextMenu', $event, { id: org.id, name: org.name, isRoot: false })"
        draggable="true"
        @dragstart="emit('handleOrgDragStart', $event, org.id)"
        @dragover.prevent="emit('handleOrgDragOver', $event, org.id)"
        @dragleave="emit('handleOrgDragLeave')"
        @drop.prevent="emit('handleOrgDrop', $event, org.id)"
        @dragend="emit('handleOrgDragEnd')"
      >
        <DownOutlined v-if="org.hasChildren && isOrgExpanded(org.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" />
        <RightOutlined v-else-if="org.hasChildren && !isOrgExpanded(org.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" />
        <span v-else class="w-3"></span>
        <FolderOutlined v-if="org.hasChildren && !isOrgExpanded(org.id)" class="text-sm" />
        <FolderOpenOutlined v-else-if="org.hasChildren && isOrgExpanded(org.id)" class="text-sm" />
        <FileTextOutlined v-else class="text-sm text-slate-400" />
        <span class="flex-1 truncate">{{ org.name }}</span>
        <span class="text-xs text-slate-400">({{ org.count }})</span>
      </div>
    </template>

    <!-- Context Menu -->
    <div
      v-if="showOrgContextMenu"
      class="fixed z-50 bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[140px]"
      :style="{ left: `${orgContextMenuPosition.x}px`, top: `${orgContextMenuPosition.y}px` }"
      @click.stop
    >
      <div
        @click.stop="emit('openCreateOrgModal', orgContextMenuTarget?.id || null)"
        class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
      >
        <FolderAddOutlined class="text-sm" />
        创建节点
      </div>
      <template v-if="orgContextMenuTarget && !orgContextMenuTarget.isRoot">
        <div
          @click.stop="emit('openRenameOrgModal', orgContextMenuTarget)"
          class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
        >
          <EditOutlined class="text-sm" />
          重命名节点
        </div>
        <div class="border-t border-slate-100 my-1"></div>
        <div
          @click.stop="emit('handleDeleteOrg', orgContextMenuTarget)"
          class="px-4 py-2 text-sm text-red-500 hover:bg-red-50 cursor-pointer flex items-center gap-2"
        >
          <DeleteOutlined class="text-sm" />
          删除节点
        </div>
      </template>
    </div>
  </div>
</template>