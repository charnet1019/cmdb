<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { UserOutlined, LockOutlined, EyeOutlined, EyeInvisibleOutlined, LoadingOutlined, DatabaseOutlined, CheckCircleOutlined, SafetyOutlined, QrcodeOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { getPublicSettings } from '@/api/settings'
import { getMFASetupQR } from '@/api/auth'
import type { MustChangePasswordData } from '@/types'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// Form state
const loading = ref(false)
const formState = ref({
  username: '',
  password: '',
  remember: false
})

// Password visibility
const showPassword = ref(false)

// MFA state
const mfaMode = ref(false)
const mfaSetupMode = ref(false)  // true = first-time binding flow
const mfaCode = ref('')
const mfaLoading = ref(false)

// Force change password state
const forceChangeMode = ref(false)
const forceChangeLoading = ref(false)
const forceChangeForm = ref({
  new_password: '',
  confirm_password: '',
})
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)

// MFA setup QR state
const setupQRCode = ref('')
const setupSecret = ref('')
const setupQRLoading = ref(false)

// Branding settings
const branding = ref({
  site_title: '' as string,
  login_subtitle: '' as string,
  logo_image: null as string | null,
  login_background_image: null as string | null,
  copyright_text: '' as string,
  beian_number: '' as string,
  beian_url: '' as string,
})

// Toggle password visibility
function togglePasswordVisibility() {
  showPassword.value = !showPassword.value
}

// Fetch public branding settings
async function fetchBranding() {
  try {
    const data = await getPublicSettings()
    if (data.site_title !== undefined) branding.value.site_title = data.site_title
    if (data.login_subtitle !== undefined) branding.value.login_subtitle = data.login_subtitle
    if (data.logo_image !== undefined) branding.value.logo_image = data.logo_image
    if (data.login_background_image !== undefined) branding.value.login_background_image = data.login_background_image
    if (data.copyright_text !== undefined) branding.value.copyright_text = data.copyright_text
    if (data.beian_number !== undefined) branding.value.beian_number = data.beian_number
    if (data.beian_url !== undefined) branding.value.beian_url = data.beian_url
  } catch {
    // Use defaults on error
  }
}

// Handle login
async function handleLogin() {
  if (!formState.value.username || !formState.value.password) {
    message.error('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    const response = await authStore.login(
      formState.value.username,
      formState.value.password,
      formState.value.remember
    )

    // Check if must change password
    if ((response as MustChangePasswordData).must_change_password) {
      forceChangeMode.value = true
      forceChangeForm.value = { new_password: '', confirm_password: '' }
      loading.value = false
      return
    }

    // Check if MFA is required
    if ((response as any).requires_mfa) {
      mfaMode.value = true
      mfaCode.value = ''
      loading.value = false

      // If setup mode, fetch QR code
      if ((response as any).setup) {
        mfaSetupMode.value = true
        fetchSetupQR()
      } else {
        mfaSetupMode.value = false
      }
      return
    }

    message.success('登录成功')

    // Redirect to intended page or dashboard
    const redirect = route.query.redirect as string || '/dashboard'
    router.push(redirect)
  } catch (error: any) {
    message.error(error.response?.data?.detail || '登录失败，请检查用户名和密码')
  } finally {
    loading.value = false
  }
}

// Fetch QR code for MFA setup
async function fetchSetupQR() {
  const userId = authStore.pendingMFAUserId
  if (!userId) return

  setupQRLoading.value = true
  try {
    const data = await getMFASetupQR(userId)
    setupQRCode.value = data.qr_code
    setupSecret.value = data.mfa_secret
  } catch (error: any) {
    message.error(error.response?.data?.detail || '获取二维码失败')
  } finally {
    setupQRLoading.value = false
  }
}

// Handle MFA verification
async function handleMFAVerify() {
  if (!mfaCode.value || mfaCode.value.length !== 6) {
    message.error('请输入6位验证码')
    return
  }

  mfaLoading.value = true
  try {
    await authStore.verifyMFA(mfaCode.value, mfaSetupMode.value)
    message.success('登录成功')

    // Redirect to intended page or dashboard
    const redirect = route.query.redirect as string || '/dashboard'
    router.push(redirect)
  } catch (error: any) {
    message.error(error.response?.data?.detail || 'MFA 验证码错误')
    mfaCode.value = ''
  } finally {
    mfaLoading.value = false
  }
}

// Back to password login
function backToLogin() {
  mfaMode.value = false
  mfaSetupMode.value = false
  forceChangeMode.value = false
  mfaCode.value = ''
  setupQRCode.value = ''
  setupSecret.value = ''
  forceChangeForm.value = { new_password: '', confirm_password: '' }
  authStore.clearPendingMFA()
  authStore.clearPendingForceChange()
}

// Handle force password change
async function handleForceChangePassword() {
  if (!forceChangeForm.value.new_password || !forceChangeForm.value.confirm_password) {
    message.error('请输入新密码并确认')
    return
  }

  forceChangeLoading.value = true
  try {
    await authStore.forceChangePassword(
      forceChangeForm.value.new_password,
      forceChangeForm.value.confirm_password,
    )
    message.success('密码修改成功')

    // Redirect to intended page or dashboard
    const redirect = route.query.redirect as string || '/dashboard'
    router.push(redirect)
  } catch (error: any) {
    message.error(error.response?.data?.detail || '密码修改失败')
  } finally {
    forceChangeLoading.value = false
  }
}

onMounted(() => {
  fetchBranding()
})
</script>

<template>
  <div class="min-h-screen flex">
    <!-- Left section - Branding -->
    <div
      class="hidden lg:flex lg:w-1/2 relative overflow-hidden"
      :class="branding.login_background_image ? '' : 'bg-gradient-to-br from-primary to-primary-container'"
      :style="branding.login_background_image ? { backgroundImage: `url(${branding.login_background_image})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}"
    >
      <!-- Overlay for readability when background image is set -->
      <div v-if="branding.login_background_image" class="absolute inset-0 bg-black/30" />

      <!-- Background pattern (only when no image) -->
      <div v-else class="absolute inset-0 opacity-20">
        <svg class="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
              <path d="M 10 0 L 0 0 0 10" fill="none" stroke="white" stroke-width="0.5"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      <!-- Content -->
      <div class="relative z-10 flex flex-col items-center justify-center w-full p-12">
        <!-- Logo -->
        <div class="bg-white/10 backdrop-blur-xl border border-white/20 rounded-full p-8 mb-8">
          <img
            v-if="branding.logo_image"
            :src="branding.logo_image"
            class="w-16 h-16 object-contain"
            alt="Logo"
          />
          <DatabaseOutlined v-else class="text-white text-5xl" />
        </div>

        <!-- Title -->
        <h1 v-if="branding.site_title" class="text-4xl font-bold text-white mb-4 font-headline">{{ branding.site_title }}</h1>
        <p v-if="branding.login_subtitle" class="text-white/80 text-center max-w-md text-lg">
          {{ branding.login_subtitle }}
        </p>

        <!-- Features -->
        <div class="mt-12 space-y-4">
          <div class="flex items-center gap-3 text-white/90">
            <CheckCircleOutlined class="text-white/90" />
            <span>统一管理IT基础设施资产</span>
          </div>
          <div class="flex items-center gap-3 text-white/90">
            <CheckCircleOutlined class="text-white/90" />
            <span>凭证加密存储与访问控制</span>
          </div>
          <div class="flex items-center gap-3 text-white/90">
            <CheckCircleOutlined class="text-white/90" />
            <span>完整的操作审计日志</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Right section - Login form -->
    <div class="flex-1 flex flex-col items-center justify-center relative p-8 bg-surface">
      <div class="w-full max-w-md">
        <!-- Welcome text -->
        <div class="mb-8">
          <template v-if="!mfaMode && !forceChangeMode">
            <h2 class="text-2xl font-bold text-slate-900 mb-2">欢迎回来</h2>
            <p class="text-slate-500">请登录您的账户继续访问</p>
          </template>
        </div>

        <!-- Login form -->
        <form v-if="!mfaMode && !forceChangeMode" @submit.prevent="handleLogin" autocomplete="on" class="space-y-6">
          <!-- Username -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">用户名</label>
            <div class="relative">
              <UserOutlined class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                v-model="formState.username"
                type="text"
                placeholder="请输入用户名或邮箱"
                autocomplete="username"
                class="input-field pl-12"
              />
            </div>
          </div>

          <!-- Password -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">密码</label>
            <div class="relative">
              <LockOutlined class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                v-model="formState.password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="请输入密码"
                autocomplete="current-password"
                class="input-field pl-12 pr-12"
              />
              <button
                type="button"
                @click="togglePasswordVisibility"
                class="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <component :is="showPassword ? EyeInvisibleOutlined : EyeOutlined" />
              </button>
            </div>
          </div>

          <!-- Remember -->
          <div>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                v-model="formState.remember"
                type="checkbox"
                class="w-4 h-4 rounded border-slate-300 text-primary focus:ring-primary"
              />
              <span class="text-sm text-slate-600">记住密码</span>
            </label>
          </div>

          <!-- Submit button -->
          <button
            type="submit"
            :disabled="loading"
            class="btn-primary w-full py-3.5 flex items-center justify-center gap-2"
          >
            <LoadingOutlined v-if="loading" spin class="text-xl" />
            <span v-else>登录</span>
          </button>
        </form>

        <!-- MFA Verification form -->
        <form v-else-if="mfaMode" @submit.prevent="handleMFAVerify" class="space-y-6">
          <!-- Setup mode (first-time binding) -->
          <template v-if="mfaSetupMode">
            <div class="text-center mb-6">
              <div class="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-3">
                <QrcodeOutlined class="text-primary text-3xl" />
              </div>
              <h3 class="text-lg font-semibold text-slate-900">绑定验证器</h3>
              <p class="text-sm text-slate-500 mt-1">打开您的验证器应用，扫描以下二维码</p>
            </div>

            <!-- QR Code -->
            <div v-if="setupQRLoading" class="flex justify-center py-8">
              <LoadingOutlined class="text-primary text-3xl" />
            </div>
            <div v-else-if="setupQRCode" class="flex flex-col items-center">
              <div class="p-4 bg-white border border-slate-200 rounded-xl inline-block">
                <img :src="setupQRCode" alt="MFA QR Code" class="w-48 h-48" />
              </div>
              <div class="mt-4 w-full text-left">
                <p class="text-xs font-medium text-slate-700 mb-1">Secret（如无法扫码可手动输入）：</p>
                <p class="text-xs font-mono bg-slate-50 px-3 py-2 rounded text-slate-600 select-all break-all">
                  {{ setupSecret }}
                </p>
              </div>
            </div>

            <!-- MFA Code Input -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-2">验证码</label>
              <p class="text-xs text-slate-500 mb-2">扫码后输入验证器显示的 6 位数字</p>
              <input
                v-model="mfaCode"
                type="text"
                inputmode="numeric"
                maxlength="6"
                placeholder="请输入6位验证码"
                autocomplete="one-time-code"
                class="input-field text-center text-2xl tracking-widest"
              />
            </div>
          </template>

          <!-- Normal MFA verification (already bound) -->
          <template v-else>
            <div class="text-center mb-6">
              <div class="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-3">
                <SafetyOutlined class="text-primary text-3xl" />
              </div>
              <h3 class="text-lg font-semibold text-slate-900">两步验证</h3>
              <p class="text-sm text-slate-500 mt-1">请输入您验证器应用中的 6 位验证码</p>
            </div>

            <!-- MFA Code -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-2">验证码</label>
              <input
                v-model="mfaCode"
                type="text"
                inputmode="numeric"
                maxlength="6"
                placeholder="请输入6位验证码"
                autocomplete="one-time-code"
                class="input-field text-center text-2xl tracking-widest"
              />
            </div>
          </template>

          <!-- Submit button -->
          <button
            type="submit"
            :disabled="mfaLoading"
            class="btn-primary w-full py-3.5 flex items-center justify-center gap-2"
          >
            <LoadingOutlined v-if="mfaLoading" spin class="text-xl" />
            <span v-else>{{ mfaSetupMode ? '绑定并登录' : '验证' }}</span>
          </button>

          <!-- Back button -->
          <button
            type="button"
            @click="backToLogin"
            class="w-full text-sm text-slate-500 hover:text-slate-700 transition-colors"
          >
            返回登录
          </button>
        </form>

        <!-- Force Change Password form -->
        <form v-else-if="forceChangeMode" @submit.prevent="handleForceChangePassword" class="space-y-6">
          <div class="text-center mb-6">
            <div class="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <LockOutlined class="text-amber-600 text-3xl" />
            </div>
            <h3 class="text-lg font-semibold text-slate-900">首次登录，请修改密码</h3>
            <p class="text-sm text-slate-500 mt-1">为了您的账户安全，请设置新密码</p>
          </div>

          <!-- New Password -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">新密码</label>
            <div class="relative">
              <LockOutlined class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                v-model="forceChangeForm.new_password"
                :type="showNewPassword ? 'text' : 'password'"
                placeholder="请输入新密码"
                autocomplete="new-password"
                class="input-field pl-12 pr-12"
              />
              <button
                type="button"
                @click="showNewPassword = !showNewPassword"
                class="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <component :is="showNewPassword ? EyeInvisibleOutlined : EyeOutlined" />
              </button>
            </div>
          </div>

          <!-- Confirm Password -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">确认密码</label>
            <div class="relative">
              <LockOutlined class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                v-model="forceChangeForm.confirm_password"
                :type="showConfirmPassword ? 'text' : 'password'"
                placeholder="请再次输入新密码"
                autocomplete="new-password"
                class="input-field pl-12 pr-12"
              />
              <button
                type="button"
                @click="showConfirmPassword = !showConfirmPassword"
                class="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <component :is="showConfirmPassword ? EyeInvisibleOutlined : EyeOutlined" />
              </button>
            </div>
          </div>

          <!-- Submit button -->
          <button
            type="submit"
            :disabled="forceChangeLoading"
            class="btn-primary w-full py-3.5 flex items-center justify-center gap-2"
          >
            <LoadingOutlined v-if="forceChangeLoading" spin class="text-xl" />
            <span v-else>修改密码</span>
          </button>

          <!-- Back button -->
          <button
            type="button"
            @click="backToLogin"
            class="w-full text-sm text-slate-500 hover:text-slate-700 transition-colors"
          >
            返回登录
          </button>
        </form>
      </div>

      <!-- Footer -->
      <div class="absolute bottom-0 left-0 right-0 p-6 text-center text-sm text-slate-400 space-y-1">
        <p v-if="branding.copyright_text || branding.beian_number">
          <span v-if="branding.copyright_text" v-html="branding.copyright_text" />
          <span v-if="branding.copyright_text && branding.beian_number" class="mx-2">·</span>
          <a v-if="branding.beian_number && branding.beian_url" :href="branding.beian_url" target="_blank" rel="noopener noreferrer" class="hover:text-primary">
            {{ branding.beian_number }}
          </a>
          <span v-if="branding.beian_number && !branding.beian_url">{{ branding.beian_number }}</span>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Additional styles if needed */
</style>