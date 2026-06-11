<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import TopNavBar from '@/components/layout/TopNavBar.vue'
import SideNavBar from '@/components/layout/SideNavBar.vue'

const router = useRouter()
const authStore = useAuthStore()

const sidebarCollapsed = ref(false)

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