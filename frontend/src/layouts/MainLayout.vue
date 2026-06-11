<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import TopNavBar from '@/components/layout/TopNavBar.vue'
import SideNavBar from '@/components/layout/SideNavBar.vue'

const SIDEBAR_KEY = 'sidebar-collapsed'

const router = useRouter()
const authStore = useAuthStore()

const sidebarCollapsed = ref(
  (() => {
    try {
      return localStorage.getItem(SIDEBAR_KEY) === 'true'
    } catch {
      return false
    }
  })(),
)

watch(sidebarCollapsed, (v) => {
  try { localStorage.setItem(SIDEBAR_KEY, String(v)) } catch {}
})

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div style="min-height: 100vh; background-color: #f7f9fc;">
    <TopNavBar @toggle-sidebar="toggleSidebar" @logout="handleLogout" />
    <SideNavBar :collapsed="sidebarCollapsed" />
    <main
      class="layout-main"
      :class="sidebarCollapsed ? 'layout-main-collapsed' : 'layout-main-expanded'"
    >
      <div style="padding: 4px;">
        <RouterView />
      </div>
    </main>
  </div>
</template>