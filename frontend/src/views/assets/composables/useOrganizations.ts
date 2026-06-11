/**
 * Organizations management composable
 * Handles organization tree, context menu, drag-drop, and CRUD operations
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  getOrganizationsWithStats,
  createOrganization,
  updateOrganization,
  deleteOrganization
} from '@/api/assets'
import type { Organization } from '@/types'

export function useOrganizations() {
  // Data
  const organizations = ref<Organization[]>([])
  const rootAssetCount = ref(0)
  const totalAssetCount = ref(0)

  // Tree state
  const expandedOrgIds = ref<Set<number>>(new Set())
  const isRootExpanded = ref(true)
  const selectedOrgId = ref<number | null>(null)

  // Context menu state
  const showOrgContextMenu = ref(false)
  const orgContextMenuPosition = ref({ x: 0, y: 0 })
  const orgContextMenuTarget = ref<{ id: number | null; name: string; isRoot: boolean } | null>(null)

  // Modal state
  const showOrgModal = ref(false)
  const orgModalMode = ref<'create' | 'rename'>('create')
  const orgModalLoading = ref(false)
  const orgForm = ref({
    name: '',
    parentId: null as number | null
  })

  // Drag state
  const draggedOrgId = ref<number | null>(null)
  const dragOverOrgId = ref<number | null>(null)

  // Fetch organizations
  async function fetchOrganizations() {
    try {
      const result = await getOrganizationsWithStats()
      organizations.value = result.organizations || []
      rootAssetCount.value = result.root_asset_count || 0
      totalAssetCount.value = result.total_assets || 0
    } catch (error) {
      console.error('Failed to fetch organizations')
      organizations.value = []
      rootAssetCount.value = 0
      totalAssetCount.value = 0
    }
  }

  // Toggle functions
  function toggleOrg(orgId: number) {
    if (expandedOrgIds.value.has(orgId)) {
      expandedOrgIds.value.delete(orgId)
    } else {
      expandedOrgIds.value.add(orgId)
    }
  }

  function isOrgExpanded(orgId: number): boolean {
    return expandedOrgIds.value.has(orgId)
  }

  function toggleRootExpansion() {
    isRootExpanded.value = !isRootExpanded.value
  }

  // Selection
  function selectOrganization(orgId: number | null, callback?: () => void) {
    selectedOrgId.value = orgId
    callback?.()
  }

  // Get flattened org tree for display
  const flattenedOrgs = computed(() => {
    const result: { id: number; name: string; count: number; level: number; hasChildren: boolean }[] = []

    function flatten(orgs: Organization[], level: number = 0) {
      for (const org of orgs) {
        result.push({
          id: org.id,
          name: org.name,
          count: org.total_count || org.count || 0,
          level,
          hasChildren: (org.children?.length || 0) > 0
        })
        if (isOrgExpanded(org.id) && org.children) {
          flatten(org.children, level + 1)
        }
      }
    }

    flatten(organizations.value)
    return result
  })

  // Get all organizations as flat list for dropdown selection (with full path)
  const allOrgsForSelect = computed(() => {
    const result: { id: number | null; name: string; path: string }[] = [
      { id: null, name: 'Default', path: 'Default' }
    ]

    function flattenWithOrgPath(orgs: Organization[], parentPath: string = 'Default') {
      for (const org of orgs) {
        const path = parentPath === 'Default' ? `Default / ${org.name}` : `${parentPath} / ${org.name}`
        result.push({
          id: org.id,
          name: org.name,
          path
        })
        if (org.children && org.children.length > 0) {
          flattenWithOrgPath(org.children, path)
        }
      }
    }

    flattenWithOrgPath(organizations.value)
    return result
  })

  // Get organization path by id
  function getOrgPath(orgId: number | null): string {
    if (orgId === null) {
      return 'Default'
    }

    const orgMap = new Map<number, { name: string; parentId: number | null }>()

    function buildMap(orgs: Organization[], parentId: number | null = null) {
      for (const org of orgs) {
        orgMap.set(org.id, { name: org.name, parentId })
        if (org.children && org.children.length > 0) {
          buildMap(org.children, org.id)
        }
      }
    }

    buildMap(organizations.value)

    const pathParts: string[] = []
    let currentId: number | null = orgId

    while (currentId !== null) {
      const orgInfo = orgMap.get(currentId)
      if (orgInfo) {
        pathParts.unshift(orgInfo.name)
        currentId = orgInfo.parentId
      } else {
        break
      }
    }

    pathParts.unshift('Default')
    return pathParts.join(' / ')
  }

  // Context menu handlers
  function handleOrgContextMenu(event: MouseEvent, org: { id: number | null; name: string; isRoot: boolean }) {
    event.preventDefault()
    event.stopPropagation()
    orgContextMenuTarget.value = org
    orgContextMenuPosition.value = { x: event.clientX, y: event.clientY }
    showOrgContextMenu.value = true
  }

  function closeOrgContextMenu() {
    showOrgContextMenu.value = false
    orgContextMenuTarget.value = null
  }

  // Global click handler
  function handleGlobalClick() {
    if (showOrgContextMenu.value) {
      closeOrgContextMenu()
    }
  }

  // Modal handlers
  function openCreateOrgModal(parentId: number | null) {
    orgModalMode.value = 'create'
    orgForm.value = {
      name: '',
      parentId: parentId
    }
    showOrgModal.value = true
    closeOrgContextMenu()
  }

  function openRenameOrgModal(org: { id: number | null; name: string; isRoot: boolean } | null) {
    if (!org || org.isRoot || org.id === null) return
    orgModalMode.value = 'rename'
    orgForm.value = {
      name: org.name,
      parentId: null
    }
    orgContextMenuTarget.value = { id: org.id, name: org.name, isRoot: false }
    showOrgModal.value = true
    showOrgContextMenu.value = false
  }

  async function handleOrgModalSubmit() {
    if (!orgForm.value.name.trim()) {
      message.warning('请输入节点名称')
      return
    }

    orgModalLoading.value = true
    try {
      if (orgModalMode.value === 'create') {
        await createOrganization(orgForm.value.name, orgForm.value.parentId ?? undefined)
        message.success('节点创建成功')
      } else if (orgModalMode.value === 'rename' && orgContextMenuTarget.value?.id) {
        await updateOrganization(orgContextMenuTarget.value.id, orgForm.value.name)
        message.success('节点重命名成功')
      }
      showOrgModal.value = false
      fetchOrganizations()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败')
    } finally {
      orgModalLoading.value = false
    }
  }

  function handleDeleteOrg(org: { id: number | null; name: string; isRoot: boolean } | null) {
    closeOrgContextMenu()
    if (!org || org.isRoot || org.id === null) return

    Modal.confirm({
      title: '确认删除',
      content: `确定要删除节点 "${org.name}" 吗？删除后该节点下的所有子节点也会被删除。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      async onOk() {
        try {
          await deleteOrganization(org.id!)
          message.success('节点已删除')
          if (selectedOrgId.value === org.id) {
            selectedOrgId.value = null
          }
          fetchOrganizations()
        } catch (error: any) {
          message.error(error.response?.data?.detail || '删除失败')
        }
      }
    })
  }

  // Drag and drop handlers
  function handleOrgDragStart(event: DragEvent, orgId: number) {
    draggedOrgId.value = orgId
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move'
      event.dataTransfer.setData('text/plain', String(orgId))
    }
  }

  function handleOrgDragOver(event: DragEvent, orgId: number | null) {
    event.preventDefault()
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = 'move'
    }
    dragOverOrgId.value = orgId
  }

  function handleOrgDragLeave() {
    dragOverOrgId.value = null
  }

  async function handleOrgDrop(event: DragEvent, targetOrgId: number | null) {
    event.preventDefault()
    dragOverOrgId.value = null

    if (draggedOrgId.value === null || draggedOrgId.value === targetOrgId) {
      draggedOrgId.value = null
      return
    }

    // Reorder not yet implemented — just reset drag state
    draggedOrgId.value = null
  }

  function handleOrgDragEnd() {
    draggedOrgId.value = null
    dragOverOrgId.value = null
  }

  // Setup and cleanup
  onMounted(() => {
    document.addEventListener('click', handleGlobalClick)
  })

  onUnmounted(() => {
    document.removeEventListener('click', handleGlobalClick)
  })

  return {
    // State
    organizations,
    rootAssetCount,
    totalAssetCount,
    expandedOrgIds,
    isRootExpanded,
    selectedOrgId,
    flattenedOrgs,
    allOrgsForSelect,
    showOrgContextMenu,
    orgContextMenuPosition,
    orgContextMenuTarget,
    showOrgModal,
    orgModalMode,
    orgModalLoading,
    orgForm,
    draggedOrgId,
    dragOverOrgId,

    // Actions
    fetchOrganizations,
    toggleOrg,
    isOrgExpanded,
    toggleRootExpansion,
    selectOrganization,
    getOrgPath,
    handleOrgContextMenu,
    closeOrgContextMenu,
    openCreateOrgModal,
    openRenameOrgModal,
    handleOrgModalSubmit,
    handleDeleteOrg,
    handleOrgDragStart,
    handleOrgDragOver,
    handleOrgDragLeave,
    handleOrgDrop,
    handleOrgDragEnd
  }
}