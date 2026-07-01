<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { UserOutlined, LockOutlined, EyeOutlined, EyeInvisibleOutlined, LoadingOutlined, DatabaseOutlined, CheckCircleOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { getPublicSettings } from '@/api/settings'

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
    await authStore.login(
      formState.value.username,
      formState.value.password,
      formState.value.remember
    )

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
    <div class="flex-1 flex items-center justify-center p-8 bg-surface">
      <div class="w-full max-w-md">
        <!-- Welcome text -->
        <div class="mb-8">
          <h2 class="text-2xl font-bold text-slate-900 mb-2">欢迎回来</h2>
          <p class="text-slate-500">请登录您的账户继续访问</p>
        </div>

        <!-- Login form -->
        <form @submit.prevent="handleLogin" autocomplete="on" class="space-y-6">
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

          <!-- Remember & Forgot -->
          <div class="flex items-center justify-between">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                v-model="formState.remember"
                type="checkbox"
                class="w-4 h-4 rounded border-slate-300 text-primary focus:ring-primary"
              />
              <span class="text-sm text-slate-600">记住该设备</span>
            </label>
            <a href="#" class="text-sm text-primary hover:underline">忘记密码?</a>
          </div>

          <!-- Submit button -->
          <button
            type="submit"
            :disabled="loading"
            class="btn-primary w-full py-3.5 flex items-center justify-center gap-2"
          >
            <LoadingOutlined v-if="loading" spin class="text-xl" />
            <span v-else>立即登录</span>
          </button>
        </form>

        <!-- Footer -->
        <div class="mt-8 pt-6 border-t border-slate-200 text-center text-sm text-slate-500 space-y-2">
          <p v-if="branding.copyright_text" class="text-slate-400">{{ branding.copyright_text }}</p>
          <p v-if="branding.beian_number">
            <a v-if="branding.beian_url" :href="branding.beian_url" target="_blank" rel="noopener noreferrer" class="hover:text-primary">
              {{ branding.beian_number }}
            </a>
            <span v-else>{{ branding.beian_number }}</span>
          </p>
          <p>
            <a href="#" class="hover:text-primary">安全策略</a>
            <span class="mx-2">·</span>
            <a href="#" class="hover:text-primary">服务条款</a>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Additional styles if needed */
</style>