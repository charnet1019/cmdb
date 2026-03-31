<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { ref, watch } from 'vue'

defineProps<{
  collapsed?: boolean
}>()

const route = useRoute()
const router = useRouter()

// 当前展开的父菜单ID（手风琴模式：只允许一个展开）
const expandedParentId = ref<string | null>(null)

const menuItems = [
  { id: 'dashboard', icon: 'dashboard', label: '仪表盘', path: '/dashboard' },
  {
    id: 'assets', icon: 'inventory_2', label: '资产管理',
    children: [{ id: 'assets-list', label: '资产列表', path: '/assets' }]
  },
  {
    id: 'users', icon: 'group', label: '用户管理',
    children: [
      { id: 'users-list', label: '用户', path: '/users' },
      { id: 'users-groups', label: '用户组', path: '/users/groups' }
    ]
  },
  {
    id: 'permissions', icon: 'verified_user', label: '权限管理',
    children: [{ id: 'authorizations', label: '资产授权', path: '/permissions/authorizations' }]
  },
  {
    id: 'logs', icon: 'history_edu', label: '日志审计',
    children: [
      { id: 'logs-login', label: '登录日志', path: '/logs/login' },
      { id: 'logs-operation', label: '操作日志', path: '/logs/operation' },
      { id: 'logs-password', label: '改密日志', path: '/logs/password' }
    ]
  },
  { id: 'settings', icon: 'settings', label: '系统设置', path: '/settings' }
]

function navigateTo(path: string) {
  router.push(path)
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
  for (const item of menuItems) {
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
    <nav style="padding: 12px;">
      <template v-for="item in menuItems" :key="item.id">
        <!-- Single item (无子菜单) -->
        <div
          v-if="!item.children"
          @click="navigateTo(item.path)"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
        >
          <span class="material-symbols-outlined" style="font-size: 20px;">{{ item.icon }}</span>
          <span v-if="!collapsed" style="font-size: 14px;">{{ item.label }}</span>
        </div>

        <!-- Parent with children -->
        <div v-else>
          <!-- 父菜单项：点击展开/折叠 -->
          <div
            @click="toggleParent(item)"
            class="nav-item"
            :class="{ active: isParentSelfActive(item), expanded: hasActiveChild(item) }"
          >
            <span class="material-symbols-outlined" style="font-size: 20px;">{{ item.icon }}</span>
            <span v-if="!collapsed" style="font-size: 14px; flex: 1;">{{ item.label }}</span>
            <!-- 展开/折叠箭头 -->
            <span v-if="!collapsed" class="material-symbols-outlined" style="font-size: 16px; transition: transform 0.2s;" :style="{ transform: isParentExpanded(item) ? 'rotate(180deg)' : 'rotate(0deg)' }">
              expand_more
            </span>
          </div>

          <!-- 子菜单：仅当父菜单展开时显示 -->
          <div
            v-if="!collapsed && isParentExpanded(item)"
            style="margin-left: 16px; padding-left: 16px; border-left: 1px solid #f1f5f9; margin-top: 4px;"
          >
            <div
              v-for="child in item.children"
              :key="child.id"
              @click.stop="navigateTo(child.path)"
              class="nav-item"
              :class="{ active: isActive(child.path) }"
              style="font-size: 12px; padding: 8px 16px;"
            >
              {{ child.label }}
            </div>
          </div>
        </div>
      </template>
    </nav>
  </aside>
</template>