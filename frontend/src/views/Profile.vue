<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { UserOutlined, LockOutlined, MailOutlined, PhoneOutlined, IdcardOutlined, TeamOutlined, KeyOutlined, ClockCircleOutlined, EnvironmentOutlined, SafetyOutlined, EyeOutlined, EyeInvisibleOutlined, CameraOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { getUser, updateUser } from '@/api/users'
import { changePassword, uploadAvatar, deleteAvatar } from '@/api/auth'
import { formatDateTime } from '@/utils/datetime'

const authStore = useAuthStore()

const route = useRoute()
const router = useRouter()
const activeTab = computed({
  get: () => (route.query.tab as 'info' | 'password') || 'info',
  set: (value: 'info' | 'password') => {
    router.push({ query: { ...route.query, tab: value } })
  },
})

// User detail data
const userDetails = ref<{
  id: number
  username: string
  email: string
  full_name: string | null
  phone: string | null
  avatar_url: string | null
  is_active: boolean
  mfa_enabled: boolean
  last_login_at: string | null
  created_at: string
  groups: { id: number; name: string }[]
} | null>(null)

// Edit form
const editForm = ref({
  full_name: '',
  email: '',
  phone: '',
})

const loading = ref(false)
const saving = ref(false)
const isEditing = ref(false)

// Avatar upload
const avatarUploading = ref(false)
const avatarInput = ref<HTMLInputElement | null>(null)

function triggerAvatarUpload() {
  avatarInput.value?.click()
}

async function handleAvatarUpload(file: File) {
  const allowedTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
  if (!allowedTypes.includes(file.type)) {
    message.warning('仅支持 PNG、JPG、GIF、WebP 格式')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    message.warning('头像大小不能超过 5MB')
    return
  }
  avatarUploading.value = true
  try {
    const result = await uploadAvatar(file)
    const newUrl = result?.avatar_url
    if (newUrl && userDetails.value) {
      userDetails.value = { ...userDetails.value, avatar_url: newUrl }
      authStore.user = { ...(authStore.user as any), avatar_url: newUrl }
    }
    message.success('头像上传成功')
  } catch (error: any) {
    // Upload likely succeeded on server but response parsing failed — refetch to sync state
    try {
      await fetchUserDetail()
      if (userDetails.value?.avatar_url) {
        authStore.user = { ...(authStore.user as any), avatar_url: userDetails.value.avatar_url }
        message.success('头像上传成功')
        return
      }
    } catch { /* fall through */ }
    const errMsg = error?.response?.data?.detail || error?.message || '上传失败'
    message.error(typeof errMsg === 'string' ? errMsg : '上传失败')
  } finally {
    avatarUploading.value = false
    if (avatarInput.value) avatarInput.value.value = ''
  }
}

async function removeAvatar() {
  Modal.confirm({
    title: '确认移除',
    content: '移除后将恢复为默认头像，确定继续吗？',
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        await deleteAvatar()
        await fetchUserDetail()
        authStore.user = { ...(authStore.user as any), avatar_url: null }
        message.success('头像已移除')
      } catch (error: any) {
        message.error(error.response?.data?.detail || '移除失败')
      }
    },
  })
}

// Password form
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})
const changingPassword = ref(false)

// Password field visibility
const showPassword = ref({
  old_password: false,
  new_password: false,
  confirm_password: false,
})

function togglePassword(field: keyof typeof showPassword.value) {
  showPassword.value[field] = !showPassword.value[field]
}

// Permission label map
const permLabels: Record<string, string> = {
  view: '查看资产',
  manage: '管理资产',
  view_users: '查看用户',
  user_mgmt: '用户管理',
  sys_config: '系统设置',
  audit_log: '日志审计',
  view_pwd: '查看密码',
}

async function fetchUserDetail() {
  const userId = authStore.user?.id
  if (!userId) return
  loading.value = true
  try {
    const data = await getUser(userId)
    userDetails.value = data
    editForm.value = {
      full_name: data.full_name || '',
      email: data.email || '',
      phone: data.phone || '',
    }
  } catch {
    message.error('获取用户信息失败')
  } finally {
    loading.value = false
  }
}

function startEdit() {
  isEditing.value = true
}

function cancelEdit() {
  isEditing.value = false
  if (userDetails.value) {
    editForm.value = {
      full_name: userDetails.value.full_name || '',
      email: userDetails.value.email || '',
      phone: userDetails.value.phone || '',
    }
  }
}

async function saveProfile() {
  if (!userDetails.value) return
  saving.value = true
  try {
    const data = await updateUser(userDetails.value.id, {
      full_name: editForm.value.full_name,
      email: editForm.value.email,
      phone: editForm.value.phone,
    })
    userDetails.value = data
    if (data.email !== authStore.user?.email) {
      authStore.user = { ...(authStore.user as any), email: data.email }
    }
    isEditing.value = false
    message.success('个人信息已更新')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function changePwd() {
  if (!passwordForm.value.new_password || !passwordForm.value.old_password || !passwordForm.value.confirm_password) {
    message.warning('请填写完整')
    return
  }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    message.warning('两次输入的新密码不一致')
    return
  }
  changingPassword.value = true
  try {
    await changePassword({
      old_password: passwordForm.value.old_password,
      new_password: passwordForm.value.new_password,
      confirm_password: passwordForm.value.confirm_password,
    })
    message.success('密码修改成功')
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
    showPassword.value = { old_password: false, new_password: false, confirm_password: false }
  } catch (error: any) {
    message.error(error.response?.data?.detail || '修改密码失败')
  } finally {
    changingPassword.value = false
  }
}

// Computed avatar URL for display
const avatarUrl = computed(() => {
  return userDetails.value?.avatar_url || authStore.user?.avatar_url || null
})

onMounted(() => {
  fetchUserDetail()
})
</script>

<template>
  <div class="space-y-4">
    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <!-- Tabs -->
      <div class="border-b border-slate-100">
        <nav class="flex">
          <button
            @click="activeTab = 'info'"
            :class="activeTab === 'info' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'"
            class="px-6 py-4 text-sm font-medium border-b-2 -mb-px transition-colors flex items-center gap-2"
          >
            <UserOutlined class="text-lg" />
            个人信息
          </button>
          <button
            @click="activeTab = 'password'"
            :class="activeTab === 'password' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'"
            class="px-6 py-4 text-sm font-medium border-b-2 -mb-px transition-colors flex items-center gap-2"
          >
            <LockOutlined class="text-lg" />
            修改密码
          </button>
        </nav>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="p-12 text-center text-slate-500">
        <div class="animate-spin text-3xl mb-2">⟳</div>
        <p class="text-sm">加载中...</p>
      </div>

      <!-- Personal Info Tab -->
      <div v-else-if="activeTab === 'info' && userDetails" class="p-6 space-y-6">
        <!-- Avatar Section -->
        <div class="flex items-center gap-5 p-5 bg-slate-50 rounded-xl">
          <div class="relative group flex-shrink-0">
            <div class="w-20 h-20 rounded-full bg-primary flex items-center justify-center overflow-hidden" :class="avatarUrl ? 'bg-slate-200' : ''">
              <img
                v-if="avatarUrl"
                :src="avatarUrl"
                :key="avatarUrl"
                class="w-full h-full object-cover"
                alt="头像"
              />
              <span v-else class="text-white font-bold text-3xl">
                {{ userDetails.full_name?.[0] || userDetails.username?.[0]?.toUpperCase() }}
              </span>
            </div>
            <!-- Upload overlay -->
            <div
              @click="triggerAvatarUpload"
              class="absolute bottom-0 right-0 w-7 h-7 rounded-full bg-primary flex items-center justify-center cursor-pointer shadow-md opacity-0 group-hover:opacity-100 transition-opacity"
              :class="avatarUploading ? 'opacity-50 cursor-not-allowed' : ''"
            >
              <CameraOutlined v-if="!avatarUploading" class="text-white text-xs" />
              <span v-else class="text-white text-xs animate-spin">⟳</span>
            </div>
            <!-- Remove overlay (only when avatar exists) -->
            <div
              v-if="avatarUrl"
              @click="removeAvatar"
              class="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-error flex items-center justify-center cursor-pointer shadow-md opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <DeleteOutlined class="text-white text-xs" />
            </div>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <h2 class="text-lg font-semibold text-slate-900">{{ userDetails.full_name || userDetails.username }}</h2>
              <span v-if="authStore.isSuperuser" class="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded-full font-medium">超级用户</span>
            </div>
            <p class="text-sm text-slate-500 truncate">@{{ userDetails.username }}</p>
          </div>
          <button v-if="!isEditing" @click="startEdit" class="btn-secondary flex items-center gap-1 text-sm">
            编辑
          </button>
        </div>

        <!-- Hidden file input -->
        <input
          ref="avatarInput"
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          class="hidden"
          @change="($event: any) => $event.target.files[0] && handleAvatarUpload($event.target.files[0])"
        />

        <!-- Read-only View -->
        <div v-if="!isEditing" class="max-w-2xl">
          <div class="grid grid-cols-2 gap-x-8 gap-y-5">
            <!-- Username -->
            <div class="flex items-center gap-3">
              <IdcardOutlined class="text-slate-400 text-lg" />
              <div>
                <p class="text-xs text-slate-500">用户名</p>
                <p class="text-sm font-medium text-slate-900">{{ userDetails.username }}</p>
              </div>
            </div>

            <!-- Email -->
            <div class="flex items-center gap-3">
              <MailOutlined class="text-slate-400 text-lg" />
              <div>
                <p class="text-xs text-slate-500">邮箱</p>
                <p class="text-sm font-medium text-slate-900">{{ userDetails.email }}</p>
              </div>
            </div>

            <!-- Phone -->
            <div class="flex items-center gap-3">
              <PhoneOutlined class="text-slate-400 text-lg" />
              <div>
                <p class="text-xs text-slate-500">手机号</p>
                <p class="text-sm font-medium text-slate-900">{{ userDetails.phone || '未设置' }}</p>
              </div>
            </div>

            <!-- MFA Status -->
            <div class="flex items-center gap-3">
              <SafetyOutlined class="text-lg" :class="userDetails.mfa_enabled ? 'text-success' : 'text-slate-400'" />
              <div>
                <p class="text-xs text-slate-500">MFA 状态</p>
                <p class="text-sm font-medium" :class="userDetails.mfa_enabled ? 'text-success' : 'text-slate-400'">
                  {{ userDetails.mfa_enabled ? '已启用' : '未启用' }}
                </p>
              </div>
            </div>

            <!-- Groups -->
            <div class="flex items-start gap-3 col-span-2">
              <TeamOutlined class="text-slate-400 text-lg mt-0.5" />
              <div>
                <p class="text-xs text-slate-500">所属用户组</p>
                <div v-if="userDetails.groups.length" class="flex gap-1.5 mt-1 flex-wrap">
                  <span v-for="g in userDetails.groups" :key="g.id" class="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded-full">
                    {{ g.name }}
                  </span>
                </div>
                <p v-else class="text-sm text-slate-400 mt-0.5">未加入任何用户组</p>
              </div>
            </div>

            <!-- Last Login -->
            <div class="flex items-center gap-3">
              <ClockCircleOutlined class="text-slate-400 text-lg" />
              <div>
                <p class="text-xs text-slate-500">最后登录</p>
                <p class="text-sm font-medium text-slate-900">{{ userDetails.last_login_at ? formatDateTime(userDetails.last_login_at) : '无记录' }}</p>
              </div>
            </div>

            <!-- Created At -->
            <div class="flex items-center gap-3">
              <EnvironmentOutlined class="text-slate-400 text-lg" />
              <div>
                <p class="text-xs text-slate-500">创建时间</p>
                <p class="text-sm font-medium text-slate-900">{{ formatDateTime(userDetails.created_at) }}</p>
              </div>
            </div>

            <!-- Permissions -->
            <div class="flex items-start gap-3 col-span-2">
              <KeyOutlined class="text-slate-400 text-lg mt-0.5" />
              <div>
                <p class="text-xs text-slate-500">权限</p>
                <div v-if="authStore.isSuperuser" class="text-sm text-slate-600 mt-0.5">
                  超级用户 — 拥有所有权限
                </div>
                <div v-else class="flex gap-1.5 mt-1 flex-wrap">
                  <span v-for="p in authStore.permissions" :key="p" class="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded-full">
                    {{ permLabels[p] || p }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Edit Form -->
        <div v-else class="max-w-2xl space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">姓名</label>
            <input
              v-model="editForm.full_name"
              type="text"
              class="input-field"
              placeholder="请输入姓名"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">邮箱</label>
            <input
              v-model="editForm.email"
              type="email"
              class="input-field"
              placeholder="请输入邮箱"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">手机号</label>
            <input
              v-model="editForm.phone"
              type="text"
              class="input-field"
              placeholder="请输入手机号"
            />
          </div>
          <div class="flex items-center gap-3 pt-2">
            <button @click="saveProfile" :disabled="saving" class="btn-primary">
              {{ saving ? '保存中...' : '保存' }}
            </button>
            <button @click="cancelEdit" class="btn-secondary">取消</button>
          </div>
        </div>
      </div>

      <!-- Change Password Tab -->
      <div v-else-if="activeTab === 'password'" class="p-6">
        <div class="max-w-md space-y-5">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">原密码</label>
            <div class="relative">
              <input
                v-model="passwordForm.old_password"
                :type="showPassword.old_password ? 'text' : 'password'"
                class="input-field"
                :style="{ paddingRight: showPassword.old_password ? '40px' : '' }"
                placeholder="请输入当前密码"
                autocomplete="current-password"
              />
              <button
                v-if="passwordForm.old_password"
                type="button"
                @click="togglePassword('old_password')"
                style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; color: #94a3b8; padding: 0;"
              >
                <EyeOutlined v-if="showPassword.old_password" class="text-lg" />
                <EyeInvisibleOutlined v-else class="text-lg" />
              </button>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">新密码</label>
            <div class="relative">
              <input
                v-model="passwordForm.new_password"
                :type="showPassword.new_password ? 'text' : 'password'"
                class="input-field"
                :style="{ paddingRight: showPassword.new_password ? '40px' : '' }"
                placeholder="请输入新密码"
                autocomplete="new-password"
              />
              <button
                v-if="passwordForm.new_password"
                type="button"
                @click="togglePassword('new_password')"
                style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; color: #94a3b8; padding: 0;"
              >
                <EyeOutlined v-if="showPassword.new_password" class="text-lg" />
                <EyeInvisibleOutlined v-else class="text-lg" />
              </button>
            </div>
            <p class="text-xs text-slate-500 mt-1">至少 8 位，需包含大写字母、小写字母和数字</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">确认新密码</label>
            <div class="relative">
              <input
                v-model="passwordForm.confirm_password"
                :type="showPassword.confirm_password ? 'text' : 'password'"
                class="input-field"
                :style="{ paddingRight: showPassword.confirm_password ? '40px' : '' }"
                placeholder="请再次输入新密码"
                autocomplete="new-password"
              />
              <button
                v-if="passwordForm.confirm_password"
                type="button"
                @click="togglePassword('confirm_password')"
                style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; color: #94a3b8; padding: 0;"
              >
                <EyeOutlined v-if="showPassword.confirm_password" class="text-lg" />
                <EyeInvisibleOutlined v-else class="text-lg" />
              </button>
            </div>
          </div>
          <button @click="changePwd" :disabled="changingPassword" class="btn-primary">
            {{ changingPassword ? '修改中...' : '修改密码' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
