<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { ref, watch, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  AppstoreOutlined,
  ClusterOutlined,
  TeamOutlined,
  SafetyCertificateOutlined,
  HistoryOutlined,
  SettingOutlined,
  DownOutlined
} from '@ant-design/icons-vue'

withDefaults(defineProps<{
  collapsed?: boolean
}>(), {
  collapsed: false
})

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// 当前展开的父菜单ID（手风琴模式：只允许一个展开）
const expandedParentId = ref<string | null>(null)
// 折叠状态下当前悬停的父菜单ID
const hoveredParentId = ref<string | null>(null)
// 折叠状态下当前悬停的单级菜单ID
const hoveredSingleId = ref<string | null>(null)
// 浮动面板的 top 位置（px）
const hoverPanelTop = ref<number>(0)
const hoverSingleTop = ref<number>(0)
let hoverHideTimer: ReturnType<typeof setTimeout> | null = null
// Store refs for parent menu items by id
const parentItemRefs = ref<Record<string, HTMLElement>>({})
const singleItemRefs = ref<Record<string, HTMLElement>>({})

function setParentItemRef(id: string) {
  return (el: HTMLElement | null) => { if (el) parentItemRefs.value[id] = el }
}

function setSingleItemRef(id: string) {
  return (el: HTMLElement | null) => { if (el) singleItemRefs.value[id] = el }
}

function onSingleEnter(item: any) {
  if (hoverHideTimer) { clearTimeout(hoverHideTimer); hoverHideTimer = null }
  hoveredSingleId.value = item.id
  hoveredParentId.value = null  // 清除父菜单悬停
  const el = singleItemRefs.value[item.id]
  if (el) hoverSingleTop.value = el.getBoundingClientRect().top
}

function onSingleLeave() {
  hoverHideTimer = setTimeout(() => {
    hoveredSingleId.value = null
    hoverHideTimer = null
  }, 150)
}

const allMenuItems = [
  { id: 'dashboard', icon: AppstoreOutlined, label: '仪表盘', path: '/dashboard' },
  {
    id: 'assets', icon: ClusterOutlined, label: '资产管理', permissions: ['view', 'manage'],
    children: [{ id: 'assets-list', label: '资产列表', path: '/assets' }]
  },
  {
    id: 'users', icon: TeamOutlined, label: '用户管理', permissions: ['user_mgmt'],
    children: [
      { id: 'users-list', label: '用户', path: '/users' },
      { id: 'users-groups', label: '用户组', path: '/users/groups' }
    ]
  },
  {
    id: 'permissions', icon: SafetyCertificateOutlined, label: '权限管理', permissions: ['sys_config'],
    children: [{ id: 'authorizations', label: '资产授权', path: '/permissions/authorizations' }]
  },
  {
    id: 'logs', icon: HistoryOutlined, label: '日志审计', permissions: ['audit_log'],
    children: [
      { id: 'logs-login', label: '登录日志', path: '/logs/login' },
      { id: 'logs-operation', label: '操作日志', path: '/logs/operation' },
      { id: 'logs-password', label: '改密日志', path: '/logs/password' }
    ]
  },
  { id: 'settings', icon: SettingOutlined, label: '系统设置', permissions: ['sys_config'], path: '/settings' }
]

const menuItems = computed(() => {
  if (authStore.isSuperuser) return allMenuItems

  return allMenuItems.filter(item => {
    if (!item.permissions) return true // Dashboard — always visible
    return item.permissions.some(p => authStore.hasPermission(p))
  })
})

// Reset expanded state when permissions change (menu items may disappear)
watch(menuItems, () => {
  expandedParentId.value = null
}, { deep: true })

function navigateTo(path: string) {
  router.push(path)
}

function onParentEnter(item: any) {
  if (hoverHideTimer) { clearTimeout(hoverHideTimer); hoverHideTimer = null }
  hoveredParentId.value = item.id
  hoveredSingleId.value = null  // 清除单级菜单悬停
  const el = parentItemRefs.value[item.id]
  if (el) hoverPanelTop.value = el.getBoundingClientRect().top
}

function onParentLeave(item: any) {
  hoverHideTimer = setTimeout(() => {
    if (hoveredParentId.value === item.id) {
      hoveredParentId.value = null
    }
    hoverHideTimer = null
  }, 150)
}

function isActive(path: string): boolean {
  return route.path === path
}

// 父菜单自身是否被选中（仅当父菜单有自己路径时）
function isParentSelfActive(item: any): boolean {
  return item.path && isActive(item.path)
}

// 父菜单下是否有子菜单被选中
function hasActiveChild(item: any): boolean {
  if (item.children) {
    return item.children.some((child: any) => isActive(child.path))
  }
  return false
}

// 折叠状态下，父菜单项是否应高亮（有子菜单活跃）
function isParentCollapsedActive(item: any): boolean {
  return hasActiveChild(item)
}

// 点击父菜单：展开/折叠
function toggleParent(item: any) {
  if (expandedParentId.value === item.id) {
    // 点击已展开的菜单 -> 折叠
    expandedParentId.value = null
  } else {
    // 点击其他菜单 -> 展开该菜单（自动折叠其他）
    expandedParentId.value = item.id
  }
}

// 判断父菜单是否展开
function isParentExpanded(item: any): boolean {
  return expandedParentId.value === item.id
}

// 监听路由变化：自动展开包含当前路由的父菜单
watch(() => route.path, (path) => {
  for (const item of menuItems.value) {
    if (item.children && item.children.some((child: any) => child.path === path)) {
      expandedParentId.value = item.id
      break
    }
  }
}, { immediate: true })
</script>

<template>
  <aside
    class="layout-sidebar"
    :class="collapsed ? 'layout-sidebar-collapsed' : 'layout-sidebar-expanded'"
  >
    <nav style="padding: 8px;">
      <template v-for="item in menuItems" :key="item.id">
        <!-- Single item (无子菜单) -->
        <div
          v-if="!item.children"
          :ref="setSingleItemRef(item.id)"
          class="single-menu-wrapper"
          @mouseenter="onSingleEnter(item)"
          @mouseleave="onSingleLeave"
        >
          <!-- 展开态 -->
          <div
            v-show="!collapsed"
            @click="navigateTo(item.path)"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
          >
            <component :is="item.icon" style="font-size: 20px;"/>
            <span style="font-size: 14px;">{{ item.label }}</span>
          </div>

          <!-- 折叠态：图标 -->
          <div
            v-show="collapsed"
            @click="navigateTo(item.path)"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            style="justify-content: center;"
          >
            <component :is="item.icon" style="font-size: 20px;"/>
          </div>

          <!-- 折叠态：浮动提示 -->
          <div
            v-if="collapsed && hoveredSingleId === item.id"
            class="collapsed-hover-panel collapsed-hover-tooltip"
            :style="{ top: hoverSingleTop + 'px' }"
            @mouseenter="onSingleEnter(item)"
            @mouseleave="onSingleLeave"
          >
            {{ item.label }}
          </div>
        </div>

        <!-- Parent with children -->
        <div
          v-else
          :ref="setParentItemRef(item.id)"
          class="parent-menu-wrapper"
          @mouseenter="onParentEnter(item)"
          @mouseleave="onParentLeave(item)"
        >
          <!-- 展开态：父菜单项点击展开/折叠 -->
          <div
            v-show="!collapsed"
            @click="toggleParent(item)"
            class="nav-item"
            :class="{ active: isParentSelfActive(item), expanded: hasActiveChild(item) }"
          >
            <component :is="item.icon" style="font-size: 20px;"/>
            <span style="font-size: 14px; flex: 1;">{{ item.label }}</span>
            <component :is="DownOutlined" class="nav-arrow" style="transition: transform 0.2s;" :style="{ transform: isParentExpanded(item) ? 'rotate(180deg)' : 'rotate(0deg)' }"/>
          </div>

          <!-- 折叠态：父菜单项悬停触发 -->
          <div
            v-show="collapsed"
            class="nav-item"
            :class="{ active: isParentCollapsedActive(item) }"
            style="justify-content: center; position: relative;"
          >
            <component :is="item.icon" style="font-size: 20px;"/>
          </div>

          <!-- 展开态：内联子菜单 -->
          <div
            v-if="!collapsed && isParentExpanded(item)"
            style="margin-left: 12px; padding-left: 12px; border-left: 1px solid #f1f5f9; margin-top: 4px;"
          >
            <div
              v-for="child in item.children"
              :key="child.id"
              @click.stop="navigateTo(child.path)"
              class="nav-item"
              :class="{ active: isActive(child.path) }"
              style="font-size: 12px; padding: 8px 12px;"
            >
              {{ child.label }}
            </div>
          </div>

          <!-- 折叠态：浮动子菜单 -->
          <div
            v-if="collapsed && hoveredParentId === item.id"
            class="collapsed-hover-panel"
            :style="{ top: hoverPanelTop + 'px' }"
            @mouseenter="onParentEnter(item)"
            @mouseleave="onParentLeave(item)"
          >
            <div
              v-for="child in item.children"
              :key="child.id"
              @click="navigateTo(child.path)"
              class="collapsed-hover-child"
              :class="{ active: isActive(child.path) }"
            >
              {{ child.label }}
            </div>
          </div>
        </div>
      </template>
    </nav>
  </aside>
</template>

<style scoped>
/* Parent wrapper — positions the floating panel when collapsed */
.parent-menu-wrapper,
.single-menu-wrapper {
  position: relative;
}

/* Floating panel shown on hover when collapsed */
.collapsed-hover-panel {
  position: fixed;
  left: var(--sidebar-collapsed-width);
  width: 180px;
  background-color: #ffffff;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12), 0 2px 6px rgba(0, 0, 0, 0.06);
  padding: 4px 0;
  z-index: 60;
  transition: opacity 0.15s ease;
}

.collapsed-hover-child {
  display: flex;
  align-items: center;
  padding: 8px 14px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s;
}

.collapsed-hover-child:hover {
  background-color: #f2f4f7;
  color: #0f172a;
}

.collapsed-hover-child.active {
  background-color: rgba(0, 93, 170, 0.1);
  color: #005daa;
  font-weight: 500;
}

/* Tooltip variant for single menu items */
.collapsed-hover-tooltip {
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
  line-height: 1.4;
}

/* Thinner arrow icon */
.nav-arrow :deep(svg) {
  font-size: 12px;
}
.nav-arrow :deep(path) {
  stroke-width: 1.2;
}
</style>