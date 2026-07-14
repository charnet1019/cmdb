<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { ref, onUnmounted, onMounted, computed } from 'vue'
import { MenuOutlined, BellOutlined, DownOutlined, UserOutlined, LogoutOutlined, SendOutlined, CheckOutlined } from '@ant-design/icons-vue'
import { getPublicSettings } from '@/api/settings'
import { getUsersForAuth, getGroupsForAuth } from '@/api/authorizations'

const authStore = useAuthStore()
const notificationStore = useNotificationsStore()

const emit = defineEmits<{
  (e: 'toggle-sidebar'): void
  (e: 'logout'): void
}>()

const showUserMenu = ref(false)
const showNotificationPanel = ref(false)
const showCompose = ref(false)
const notificationRoot = ref<HTMLElement | null>(null)
const siteTitle = ref('')
const notificationFilter = ref<'all' | 'unread' | 'read' | 'sent'>('all')
const recipientScope = ref<'all' | 'users' | 'groups'>('users')
const selectedUserIds = ref<number[]>([])
const selectedGroupIds = ref<number[]>([])
const notificationTitle = ref('')
const notificationContent = ref('')
const sendError = ref('')
const sendSuccess = ref('')
const userOptions = ref<Array<{ id: number; name: string; full_name: string | null }>>([])
const groupOptions = ref<Array<{ id: number; name: string }>>([])
const recipientsLoaded = ref(false)
let hideTimeout: ReturnType<typeof setTimeout> | null = null

const unreadLabel = computed(() => notificationStore.unreadCount > 99 ? '99+' : String(notificationStore.unreadCount))
const isSentNotificationFilter = computed(() => notificationFilter.value === 'sent')

async function fetchSiteTitle() {
  try {
    const data = await getPublicSettings()
    siteTitle.value = data.site_title || ''
  } catch {
    // Keep empty
  }
}

async function loadRecipients() {
  if (recipientsLoaded.value || !notificationStore.canSend) return
  const [users, groups] = await Promise.all([getUsersForAuth(), getGroupsForAuth()])
  userOptions.value = users
  groupOptions.value = groups
  recipientsLoaded.value = true
}

async function refreshNotifications() {
  if (notificationFilter.value === 'sent') {
    await notificationStore.fetchSentNotifications()
    return
  }
  await notificationStore.fetchNotifications(notificationFilter.value)
  await notificationStore.fetchUnreadCount()
}

async function toggleNotifications() {
  showNotificationPanel.value = !showNotificationPanel.value
  if (!showNotificationPanel.value) return
  showUserMenu.value = false
  await notificationStore.fetchCanSend()
  await refreshNotifications()
  await loadRecipients()
}

function closeNotifications() {
  showNotificationPanel.value = false
}

function handleDocumentPointerDown(event: PointerEvent) {
  if (!showNotificationPanel.value) return
  const target = event.target
  if (!(target instanceof Node)) return
  if (notificationRoot.value?.contains(target)) return
  closeNotifications()
}

function resetCompose() {
  recipientScope.value = 'users'
  selectedUserIds.value = []
  selectedGroupIds.value = []
  notificationTitle.value = ''
  notificationContent.value = ''
  sendError.value = ''
  sendSuccess.value = ''
}

async function submitNotification() {
  sendError.value = ''
  sendSuccess.value = ''
  const title = notificationTitle.value.trim()
  const content = notificationContent.value.trim()
  if (!title || !content) {
    sendError.value = '请填写标题和内容'
    return
  }
  if (recipientScope.value === 'users' && selectedUserIds.value.length === 0) {
    sendError.value = '请选择收件人'
    return
  }
  if (recipientScope.value === 'groups' && selectedGroupIds.value.length === 0) {
    sendError.value = '请选择收件用户组'
    return
  }

  const result = await notificationStore.sendNotification({
    title,
    content,
    recipient_scope: recipientScope.value,
    user_ids: recipientScope.value === 'users' ? selectedUserIds.value : [],
    group_ids: recipientScope.value === 'groups' ? selectedGroupIds.value : [],
  })
  sendSuccess.value = `已发送给 ${result.recipient_count} 位用户`
  resetCompose()
  showCompose.value = false
  if (notificationFilter.value === 'sent') {
    await refreshNotifications()
  }
}

async function markRead(item: any) {
  if (notificationFilter.value === 'sent') return
  await notificationStore.markRead(item)
}

async function markAllRead() {
  await notificationStore.markAllRead()
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const handleSettingsUpdated = (event: Event) => {
  const detail = (event as CustomEvent).detail as { site_title?: string }
  if (detail && 'site_title' in detail) {
    siteTitle.value = detail.site_title || ''
  }
}

onMounted(() => {
  fetchSiteTitle()
  notificationStore.fetchUnreadCount().catch(() => {})
  notificationStore.fetchCanSend().catch(() => {})
  window.addEventListener('settings:updated', handleSettingsUpdated)
  document.addEventListener('pointerdown', handleDocumentPointerDown)
})

onUnmounted(() => {
  if (hideTimeout) {
    clearTimeout(hideTimeout)
  }
  window.removeEventListener('settings:updated', handleSettingsUpdated)
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})

function handleToggleSidebar() {
  emit('toggle-sidebar')
}

function handleLogout() {
  showUserMenu.value = false
  showNotificationPanel.value = false
  emit('logout')
}

function showMenu() {
  if (hideTimeout) {
    clearTimeout(hideTimeout)
    hideTimeout = null
  }
  showNotificationPanel.value = false
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

    <div style="display: flex; align-items: center; gap: 12px;">
      <div ref="notificationRoot" style="position: relative;">
        <button class="icon-button" @click="toggleNotifications" title="站内信">
          <BellOutlined />
          <span v-if="notificationStore.unreadCount > 0" class="notification-badge">{{ unreadLabel }}</span>
        </button>

        <div v-if="showNotificationPanel" class="notification-panel">
          <div class="notification-header">
            <div>
              <div class="panel-title">站内信</div>
              <div class="panel-subtitle">{{ notificationStore.unreadCount }} 条未读</div>
            </div>
            <button v-if="notificationStore.canSend" class="primary-small" @click="showCompose = !showCompose">
              <SendOutlined />
              发送
            </button>
          </div>

          <div class="filter-row">
            <button :class="['filter-button', notificationFilter === 'all' ? 'active' : '']" @click="notificationFilter = 'all'; refreshNotifications()">全部</button>
            <button :class="['filter-button', notificationFilter === 'unread' ? 'active' : '']" @click="notificationFilter = 'unread'; refreshNotifications()">未读</button>
            <button :class="['filter-button', notificationFilter === 'read' ? 'active' : '']" @click="notificationFilter = 'read'; refreshNotifications()">已读</button>
            <button :class="['filter-button', notificationFilter === 'sent' ? 'active' : '']" @click="notificationFilter = 'sent'; refreshNotifications()">已发送</button>
            <button v-if="!isSentNotificationFilter" class="text-button" @click="markAllRead">全部已读</button>
          </div>

          <form v-if="showCompose && notificationStore.canSend" class="compose-form" @submit.prevent="submitNotification">
            <select v-model="recipientScope" class="form-control">
              <option value="users">指定用户</option>
              <option value="groups">指定用户组</option>
              <option value="all">所有用户</option>
            </select>
            <select v-if="recipientScope === 'users'" v-model="selectedUserIds" multiple class="form-control multi-select">
              <option v-for="user in userOptions" :key="user.id" :value="user.id">{{ user.full_name || user.name }}</option>
            </select>
            <select v-if="recipientScope === 'groups'" v-model="selectedGroupIds" multiple class="form-control multi-select">
              <option v-for="group in groupOptions" :key="group.id" :value="group.id">{{ group.name }}</option>
            </select>
            <input v-model="notificationTitle" class="form-control" maxlength="120" placeholder="标题" />
            <textarea v-model="notificationContent" class="form-control" rows="3" maxlength="5000" placeholder="内容"></textarea>
            <div v-if="sendError" class="form-error">{{ sendError }}</div>
            <div v-if="sendSuccess" class="form-success">{{ sendSuccess }}</div>
            <div class="compose-actions">
              <button type="button" class="secondary-small" @click="showCompose = false">取消</button>
              <button type="submit" class="primary-small" :disabled="notificationStore.sending">发送</button>
            </div>
          </form>

          <div class="notification-list">
            <div v-if="notificationStore.loading" class="empty-state">加载中...</div>
            <div v-else-if="notificationStore.items.length === 0" class="empty-state">{{ isSentNotificationFilter ? '暂无已发送记录' : '暂无站内信' }}</div>
            <template v-else>
              <button
                v-for="item in notificationStore.items"
                :key="item.id"
                class="notification-item"
                :class="{ unread: !isSentNotificationFilter && !item.read_at }"
                @click="markRead(item)"
              >
                <div class="item-main">
                  <div class="item-title">{{ item.title }}</div>
                  <div class="item-content">{{ item.content }}</div>
                  <div class="item-meta">
                    <span>{{ isSentNotificationFilter ? `已发送给 ${item.recipient_count || 0} 人` : (item.sender?.full_name || item.sender?.username || '系统') }}</span>
                    <span>{{ formatTime(item.created_at) }}</span>
                  </div>
                </div>
                <CheckOutlined v-if="!isSentNotificationFilter && item.read_at" class="read-icon" />
                <span v-else-if="!isSentNotificationFilter" class="unread-dot"></span>
              </button>
            </template>
          </div>
        </div>
      </div>

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

        <div style="position: relative;" @mouseenter="showMenu" @mouseleave="hideMenu">
          <button style="padding: 4px; border-radius: 4px; border: none; background: transparent; cursor: pointer; color: #94a3b8;">
            <DownOutlined />
          </button>

          <div
            v-show="showUserMenu"
            style="position: absolute; right: 0; top: 100%; margin-top: 4px; width: 140px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); border: 1px solid #f1f5f9; padding: 4px 0; z-index: 30;"
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
.icon-button {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #475569;
  position: relative;
}

.icon-button:hover {
  background-color: #f2f4f7;
}

.notification-badge {
  position: absolute;
  top: 1px;
  right: 0;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background-color: #b3261e;
  color: #fff;
  font-size: 10px;
  line-height: 16px;
  font-weight: 600;
}

.notification-panel {
  position: absolute;
  right: 0;
  top: 42px;
  width: min(380px, calc(100vw - 24px));
  max-height: calc(100vh - 86px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.16);
  z-index: 40;
}

.notification-header,
.filter-row,
.compose-actions,
.item-meta {
  display: flex;
  align-items: center;
}

.notification-header {
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #eef2f7;
}

.panel-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.panel-subtitle,
.item-meta {
  font-size: 12px;
  color: #64748b;
}

.filter-row {
  gap: 6px;
  padding: 10px 12px;
  border-bottom: 1px solid #eef2f7;
}

.filter-button,
.text-button,
.primary-small,
.secondary-small {
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 12px;
  cursor: pointer;
  height: 28px;
  padding: 0 10px;
}

.filter-button {
  color: #475569;
  background: #f8fafc;
}

.filter-button.active {
  color: #005daa;
  background: rgba(0, 93, 170, 0.08);
}

.text-button {
  margin-left: auto;
  color: #005daa;
  background: transparent;
}

.primary-small {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #fff;
  background: #005daa;
}

.primary-small:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.secondary-small {
  color: #475569;
  background: #f8fafc;
  border-color: #e2e8f0;
}

.compose-form {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid #eef2f7;
  background: #fbfdff;
}

.form-control {
  width: 100%;
  border: 1px solid #d6dde8;
  border-radius: 6px;
  padding: 7px 9px;
  font-size: 13px;
  color: #0f172a;
  background: #fff;
}

.multi-select {
  height: 88px;
}

.form-error,
.form-success {
  font-size: 12px;
}

.form-error {
  color: #b3261e;
}

.form-success {
  color: #0f7b45;
}

.compose-actions {
  justify-content: flex-end;
  gap: 8px;
}

.notification-list {
  overflow-y: auto;
}

.empty-state {
  padding: 24px 12px;
  text-align: center;
  color: #64748b;
  font-size: 13px;
}

.notification-item {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 11px 12px;
  border: 0;
  border-bottom: 1px solid #eef2f7;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.notification-item:hover {
  background: #f8fafc;
}

.notification-item.unread {
  background: #f7fbff;
}

.item-main {
  min-width: 0;
  flex: 1;
}

.item-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-content {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.45;
  color: #475569;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-meta {
  justify-content: space-between;
  gap: 10px;
  margin-top: 6px;
}

.unread-dot {
  width: 8px;
  height: 8px;
  margin-top: 7px;
  border-radius: 50%;
  background: #b3261e;
  flex-shrink: 0;
}

.read-icon {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 13px;
}

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
