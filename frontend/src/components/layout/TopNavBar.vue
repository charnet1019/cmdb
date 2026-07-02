<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { ref, onUnmounted, onMounted } from 'vue'
import { MenuOutlined, SearchOutlined, BellOutlined, DownOutlined, UserOutlined, LogoutOutlined } from '@ant-design/icons-vue'
import { getSettings } from '@/api/settings'

const authStore = useAuthStore()

const emit = defineEmits<{
  (e: 'toggle-sidebar'): void
  (e: 'logout'): void
}>()

const searchQuery = ref('')
const showUserMenu = ref(false)
const siteTitle = ref('')
let hideTimeout: ReturnType<typeof setTimeout> | null = null

async function fetchSiteTitle() {
  try {
    const response = await getSettings()
    siteTitle.value = response.data.site_title || ''
  } catch {
    // Keep empty
  }
}

const handleSettingsUpdated = (event: Event) => {
  const detail = (event as CustomEvent).detail as { site_title?: string }
  if (detail && 'site_title' in detail) {
    siteTitle.value = detail.site_title || ''
  }
}

onMounted(() => {
  fetchSiteTitle()
  window.addEventListener('settings:updated', handleSettingsUpdated)
})

onUnmounted(() => {
  if (hideTimeout) {
    clearTimeout(hideTimeout)
  }
  window.removeEventListener('settings:updated', handleSettingsUpdated)
})

function handleToggleSidebar() {
  emit('toggle-sidebar')
}

function handleLogout() {
  showUserMenu.value = false
  emit('logout')
}

function showMenu() {
  if (hideTimeout) {
    clearTimeout(hideTimeout)
    hideTimeout = null
  }
  showUserMenu.value = true
}

function hideMenu() {
  hideTimeout = setTimeout(() => {
    showUserMenu.value = false
  }, 300)
}
</script>

<template>
  <header class="layout-header">
    <!-- Left section -->
    <div style="display: flex; align-items: center; gap: 16px;">
      <button
        @click="handleToggleSidebar"
        style="padding: 8px; border-radius: 8px; border: none; background: transparent; cursor: pointer; color: #475569;"
      >
        <MenuOutlined />
      </button>

      <router-link to="/" style="display: flex; align-items: center; gap: 8px; text-decoration: none;">
        <div style="width: 32px; height: 32px; background: linear-gradient(to bottom right, #005daa, #0075d5); border-radius: 8px; display: flex; align-items: center; justify-content: center;">
          <span style="color: white; font-weight: 700; font-size: 14px;">C</span>
        </div>
        <span v-if="siteTitle" style="font-size: 18px; font-weight: 700; color: #0f172a;">{{ siteTitle }}</span>
      </router-link>
    </div>

    <!-- Center section - Search -->
    <div style="flex: 1; max-width: 28rem; margin: 0 32px; position: relative;">
      <SearchOutlined style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #94a3b8;" />
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索资产、用户..."
        style="width: 100%; background-color: #f2f4f7; border-radius: 8px; padding: 8px 16px 8px 40px; border: none; font-size: 14px; outline: none;"
      />
    </div>

    <!-- Right section -->
    <div style="display: flex; align-items: center; gap: 12px;">
      <!-- Notifications -->
      <button style="padding: 8px; border-radius: 8px; border: none; background: transparent; cursor: pointer; color: #475569; position: relative;">
        <BellOutlined />
        <span style="position: absolute; top: 4px; right: 4px; width: 8px; height: 8px; background-color: #B3261E; border-radius: 50%;"></span>
      </button>

      <!-- User menu -->
      <div style="display: flex; align-items: center; gap: 8px; padding-left: 12px; border-left: 1px solid #e2e8f0;">
        <div style="width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; overflow: hidden; flex-shrink: 0;" :style="authStore.user?.avatar_url ? { backgroundColor: 'transparent' } : { backgroundColor: 'rgba(0, 93, 170, 0.1)' }">
          <img
            v-if="authStore.user?.avatar_url"
            :src="authStore.user.avatar_url"
            style="width: 100%; height: 100%; object-fit: cover;"
            alt="avatar"
          />
          <span v-else style="color: #005daa; font-weight: 500; font-size: 14px;">
            {{ authStore.user?.full_name?.[0] || authStore.user?.username?.[0]?.toUpperCase() || 'U' }}
          </span>
        </div>
        <div class="user-info-desktop">
          <div style="font-size: 14px; font-weight: 500; color: #0f172a;">{{ authStore.user?.full_name || authStore.user?.username }}</div>
        </div>

        <!-- Dropdown -->
        <div style="position: relative;" @mouseenter="showMenu" @mouseleave="hideMenu">
          <button style="padding: 4px; border-radius: 4px; border: none; background: transparent; cursor: pointer; color: #94a3b8;">
            <DownOutlined />
          </button>

          <div
            v-show="showUserMenu"
            style="position: absolute; right: 0; top: 100%; margin-top: 4px; width: 140px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); border: 1px solid #f1f5f9; padding: 4px 0;"
          >
            <router-link to="/profile" @click="showUserMenu = false" class="dropdown-menu-item">
              <UserOutlined style="font-size: 14px; margin-right: 6px; vertical-align: middle;" />
              个人中心
            </router-link>
            <button @click="handleLogout" class="dropdown-menu-item">
              <LogoutOutlined style="font-size: 14px; margin-right: 6px; vertical-align: middle;" />
              退出登录
            </button>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.dropdown-menu-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 6px 12px;
  font-size: 13px;
  color: #334155;
  text-decoration: none;
  border: none;
  background: none;
  cursor: pointer;
  transition: background-color 0.15s;
}

.dropdown-menu-item:hover {
  background-color: #f2f4f7;
}
</style>