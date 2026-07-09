<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { SettingOutlined, SafetyCertificateOutlined, LoadingOutlined, SaveOutlined, InfoCircleOutlined, PictureOutlined, DatabaseOutlined, MailOutlined } from '@ant-design/icons-vue'
import { getSettings, updateSettings, uploadImage, deleteImage } from '@/api/settings'

// Loading states
const loading = ref(false)
const saving = ref(false)

// Settings data
const settings = ref<Record<string, any>>({})

// Form state
const form = ref({
  // 系统设置
  site_title: 'CMDB',
  copyright_text: '',
  beian_number: '',
  beian_url: '',
  // 日志保留
  login_log_retention: 30,
  operation_log_retention: 30,
  password_log_retention: 30,
  // 密码策略
  password_min_length: 8,
  password_require_uppercase: true,
  password_require_lowercase: true,
  password_require_digit: true,
  password_require_special: false,
  // 登录设置
  max_login_attempts: 5,
  lockout_duration: 30,
  session_timeout: 30,
  // OTP 设置
  otp_issuer_name: 'CMDB',
  // 品牌设置
  login_subtitle: '企业资产配置管理平台',
  logo_image: null as string | null,
  login_background_image: null as string | null,
  // 邮件设置
  smtp_host: '',
  smtp_port: 465,
  smtp_use_ssl: true,
  smtp_username: '',
  smtp_password: '',
  smtp_from_email: '',
  smtp_from_name: 'CMDB',
})

// Upload states
const logoUploading = ref(false)
const bgUploading = ref(false)

// File input refs for resetting after upload/clear
const logoInput = ref<HTMLInputElement | null>(null)
const bgInput = ref<HTMLInputElement | null>(null)

function resetFileInput(inputRef: typeof logoInput) {
  if (inputRef.value) inputRef.value.value = ''
}

// Text entity normalization for settings saved as plain text
function decodeTextEntities(value: string): string {
  const textarea = document.createElement('textarea')
  textarea.innerHTML = value
  return textarea.value
}

// Active tab
const route = useRoute()
const router = useRouter()

// Active tab — persisted in URL query so refreshing keeps the tab
const activeTab = computed({
  get: () => (route.query.tab as 'system' | 'security' | 'branding' | 'email') || 'system',
  set: (value: 'system' | 'security' | 'branding' | 'email') => {
    router.push({ query: { ...route.query, tab: value } })
  },
})

// Password complexity score
const passwordComplexityScore = computed(() => {
  let score = 0
  if (form.value.password_min_length >= 8) score += 1
  if (form.value.password_min_length >= 12) score += 1
  if (form.value.password_require_uppercase) score += 1
  if (form.value.password_require_lowercase) score += 1
  if (form.value.password_require_digit) score += 1
  if (form.value.password_require_special) score += 1
  return score
})

const complexityLevel = computed(() => {
  if (passwordComplexityScore.value >= 5) return { label: '强', color: 'text-success' }
  if (passwordComplexityScore.value >= 3) return { label: '中', color: 'text-yellow-600' }
  return { label: '弱', color: 'text-error' }
})

// Fetch settings
async function fetchSettings() {
  loading.value = true
  try {
    const response = await getSettings()
    settings.value = response.data

    // Populate form with settings
    if (response.data.site_title !== undefined) form.value.site_title = response.data.site_title
    if (response.data.session_timeout !== undefined) form.value.session_timeout = response.data.session_timeout
    if (response.data.copyright_text !== undefined) form.value.copyright_text = decodeTextEntities(response.data.copyright_text)
    if (response.data.beian_number !== undefined) form.value.beian_number = response.data.beian_number
    if (response.data.beian_url !== undefined) form.value.beian_url = response.data.beian_url
    if (response.data.password_min_length !== undefined) form.value.password_min_length = response.data.password_min_length
    if (response.data.password_require_uppercase !== undefined) form.value.password_require_uppercase = response.data.password_require_uppercase
    if (response.data.password_require_lowercase !== undefined) form.value.password_require_lowercase = response.data.password_require_lowercase
    if (response.data.password_require_digit !== undefined) form.value.password_require_digit = response.data.password_require_digit
    if (response.data.password_require_special !== undefined) form.value.password_require_special = response.data.password_require_special
    if (response.data.max_login_attempts !== undefined) form.value.max_login_attempts = response.data.max_login_attempts
    if (response.data.lockout_duration !== undefined) form.value.lockout_duration = response.data.lockout_duration
    if (response.data.login_subtitle !== undefined) form.value.login_subtitle = response.data.login_subtitle
    if (response.data.logo_image !== undefined) form.value.logo_image = response.data.logo_image
    if (response.data.login_background_image !== undefined) form.value.login_background_image = response.data.login_background_image
    if (response.data.login_log_retention !== undefined) form.value.login_log_retention = response.data.login_log_retention
    if (response.data.operation_log_retention !== undefined) form.value.operation_log_retention = response.data.operation_log_retention
    if (response.data.password_log_retention !== undefined) form.value.password_log_retention = response.data.password_log_retention
    if (response.data.otp_issuer_name !== undefined) form.value.otp_issuer_name = response.data.otp_issuer_name
    if (response.data.smtp_host !== undefined) form.value.smtp_host = response.data.smtp_host
    if (response.data.smtp_port !== undefined) form.value.smtp_port = response.data.smtp_port
    if (response.data.smtp_use_ssl !== undefined) form.value.smtp_use_ssl = response.data.smtp_use_ssl
    if (response.data.smtp_username !== undefined) form.value.smtp_username = response.data.smtp_username
    if (response.data.smtp_password !== undefined) form.value.smtp_password = response.data.smtp_password
    if (response.data.smtp_from_email !== undefined) form.value.smtp_from_email = response.data.smtp_from_email
    if (response.data.smtp_from_name !== undefined) form.value.smtp_from_name = response.data.smtp_from_name
  } catch (error) {
    message.error('获取设置失败')
  } finally {
    loading.value = false
  }
}

// Save settings
async function saveSettings() {
  saving.value = true
  try {
    const data: Record<string, any> = {}

    if (activeTab.value === 'system') {
      data.site_title = form.value.site_title
      data.copyright_text = decodeTextEntities(form.value.copyright_text)
      data.beian_number = form.value.beian_number
      data.beian_url = form.value.beian_url
      data.login_log_retention = form.value.login_log_retention
      data.operation_log_retention = form.value.operation_log_retention
      data.password_log_retention = form.value.password_log_retention
    } else if (activeTab.value === 'security') {
      data.password_min_length = form.value.password_min_length
      data.password_require_uppercase = form.value.password_require_uppercase
      data.password_require_lowercase = form.value.password_require_lowercase
      data.password_require_digit = form.value.password_require_digit
      data.password_require_special = form.value.password_require_special
      data.max_login_attempts = form.value.max_login_attempts
      data.lockout_duration = form.value.lockout_duration
      data.session_timeout = form.value.session_timeout
      data.otp_issuer_name = form.value.otp_issuer_name
    } else if (activeTab.value === 'branding') {
      data.login_subtitle = form.value.login_subtitle
      data.logo_image = form.value.logo_image
      data.login_background_image = form.value.login_background_image
    } else if (activeTab.value === 'email') {
      data.smtp_host = form.value.smtp_host
      data.smtp_port = form.value.smtp_port
      data.smtp_use_ssl = form.value.smtp_use_ssl
      data.smtp_username = form.value.smtp_username
      data.smtp_password = form.value.smtp_password
      data.smtp_from_email = form.value.smtp_from_email
      data.smtp_from_name = form.value.smtp_from_name
    }

    await updateSettings(data)
    message.success('设置已保存')
    window.dispatchEvent(new CustomEvent('settings:updated', { detail: data }))
  } catch (error: any) {
    message.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// Reset to defaults
function resetToDefaults() {
  if (activeTab.value === "system") {
    form.value.site_title = "CMDB"
    form.value.copyright_text = ""
    form.value.beian_number = ""
    form.value.beian_url = ""
    form.value.login_log_retention = 30
    form.value.operation_log_retention = 30
    form.value.password_log_retention = 30
  } else if (activeTab.value === "security") {
    form.value.password_min_length = 8
    form.value.password_require_uppercase = true
    form.value.password_require_lowercase = true
    form.value.password_require_digit = true
    form.value.password_require_special = false
    form.value.max_login_attempts = 5
    form.value.lockout_duration = 30
    form.value.session_timeout = 30
    form.value.otp_issuer_name = "CMDB"
  } else if (activeTab.value === "branding") {
    form.value.login_subtitle = "企业资产配置管理平台"
    form.value.logo_image = null
    form.value.login_background_image = null
  } else if (activeTab.value === "email") {
    form.value.smtp_host = ""
    form.value.smtp_port = 465
    form.value.smtp_use_ssl = true
    form.value.smtp_username = ""
    form.value.smtp_password = ""
    form.value.smtp_from_email = ""
    form.value.smtp_from_name = "CMDB"
  }
}

// Upload logo
async function handleLogoUpload(file: File) {
  logoUploading.value = true
  try {
    // Delete old logo if exists
    if (form.value.logo_image) {
      const oldFilename = form.value.logo_image.split('/').pop()
      if (oldFilename) {
        try { await deleteImage(oldFilename) } catch {}
      }
    }
    const result = await uploadImage(file)
    form.value.logo_image = result.url
    message.success('Logo 上传成功')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '上传失败')
  } finally {
    logoUploading.value = false
    resetFileInput(logoInput)
  }
}

// Upload background image
async function handleBgUpload(file: File) {
  bgUploading.value = true
  try {
    if (form.value.login_background_image) {
      const oldFilename = form.value.login_background_image.split('/').pop()
      if (oldFilename) {
        try { await deleteImage(oldFilename) } catch {}
      }
    }
    const result = await uploadImage(file)
    form.value.login_background_image = result.url
    message.success('背景图片上传成功')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '上传失败')
  } finally {
    bgUploading.value = false
    resetFileInput(bgInput)
  }
}

// Clear logo
async function clearLogo() {
  if (form.value.logo_image) {
    const filename = form.value.logo_image.split('/').pop()
    if (filename) {
      try { await deleteImage(filename) } catch {}
    }
  }
  form.value.logo_image = null
  resetFileInput(logoInput)
}

// Clear background
async function clearBackground() {
  if (form.value.login_background_image) {
    const filename = form.value.login_background_image.split('/').pop()
    if (filename) {
      try { await deleteImage(filename) } catch {}
    }
  }
  form.value.login_background_image = null
  resetFileInput(bgInput)
}

// Initial load
onMounted(() => {
  fetchSettings()
})
</script>

<template>
  <div class="space-y-4">
    <!-- Tabs -->
    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
      <div class="border-b border-slate-100">
        <nav class="flex">
          <button
            @click="activeTab = 'system'"
            :class="activeTab === 'system' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'"
            class="px-6 py-4 text-sm font-medium border-b-2 -mb-px transition-colors"
          >
            <SettingOutlined class="text-lg align-middle mr-1" />
            系统设置
          </button>
          <button
            @click="activeTab = 'security'"
            :class="activeTab === 'security' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'"
            class="px-6 py-4 text-sm font-medium border-b-2 -mb-px transition-colors"
          >
            <SafetyCertificateOutlined class="text-lg align-middle mr-1" />
            安全
          </button>
          <button
            @click="activeTab = 'branding'"
            :class="activeTab === 'branding' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'"
            class="px-6 py-4 text-sm font-medium border-b-2 -mb-px transition-colors"
          >
            <PictureOutlined class="text-lg align-middle mr-1" />
            品牌设置
          </button>
          <button
            @click="activeTab = 'email'"
            :class="activeTab === 'email' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'"
            class="px-6 py-4 text-sm font-medium border-b-2 -mb-px transition-colors"
          >
            <MailOutlined class="text-lg align-middle mr-1" />
            邮件
          </button>
        </nav>
      </div>

      <!-- Loading state -->
      <div v-if="loading" class="p-12 text-center text-slate-500">
        <LoadingOutlined class="animate-spin text-4xl" />
        <p class="mt-2">加载中...</p>
      </div>

      <!-- System Settings Tab -->
      <div v-else-if="activeTab === 'system'" class="p-6 space-y-6">
        <div class="max-w-2xl">
          <!-- Site Title -->
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">站点标题</label>
              <input
                v-model="form.site_title"
                type="text"
                class="input-field"
                placeholder="CMDB"
              />
              <p class="text-xs text-slate-500 mt-1">显示在浏览器标签和页面标题中</p>
            </div>

            <!-- Copyright -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">版权信息</label>
              <input
                v-model="form.copyright_text"
                type="text"
                class="input-field"
                placeholder="© 2026 CMDB. All rights reserved."
              />
              <p class="text-xs text-slate-500 mt-1">显示在登录页底部，留空则不显示</p>
            </div>

            <!-- Beian Number -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">备案号</label>
              <input
                v-model="form.beian_number"
                type="text"
                class="input-field"
                placeholder="京ICP备12345678号"
              />
              <p class="text-xs text-slate-500 mt-1">显示在登录页底部，留空则不显示</p>
            </div>

            <!-- Beian URL -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">备案链接</label>
              <input
                v-model="form.beian_url"
                type="text"
                class="input-field"
                placeholder="https://beian.miit.gov.cn/"
              />
              <p class="text-xs text-slate-500 mt-1">备案号点击后跳转的链接，留空则不设为链接</p>
            </div>
          </div>

          <!-- Log Retention Section -->
          <div class="border-t border-slate-100 pt-6 mt-6">
            <h3 class="text-sm font-medium text-slate-700 mb-4">日志保留</h3>
            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">登录日志保留时间</label>
                <div class="flex items-center gap-3">
                  <input
                    v-model.number="form.login_log_retention"
                    type="number"
                    min="1"
                    max="365"
                    class="input-field w-32"
                  />
                  <span class="text-slate-600">天</span>
                </div>
                <p class="text-xs text-slate-500 mt-1">超过此天数的登录日志将自动删除</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">操作日志保留时间</label>
                <div class="flex items-center gap-3">
                  <input
                    v-model.number="form.operation_log_retention"
                    type="number"
                    min="1"
                    max="365"
                    class="input-field w-32"
                  />
                  <span class="text-slate-600">天</span>
                </div>
                <p class="text-xs text-slate-500 mt-1">超过此天数的操作日志将自动删除</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">改密日志保留时间</label>
                <div class="flex items-center gap-3">
                  <input
                    v-model.number="form.password_log_retention"
                    type="number"
                    min="1"
                    max="365"
                    class="input-field w-32"
                  />
                  <span class="text-slate-600">天</span>
                </div>
                <p class="text-xs text-slate-500 mt-1">超过此天数的改密日志将自动删除</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-3 pt-4 border-t border-slate-100">
          <button @click="saveSettings" :disabled="saving" class="btn-primary flex items-center gap-2">
            <LoadingOutlined v-if="saving" class="animate-spin text-lg" />
            <SaveOutlined v-else class="text-lg" />
            {{ saving ? '保存中...' : '保存设置' }}
          </button>
          <button @click="resetToDefaults" class="btn-secondary">恢复默认</button>
        </div>
      </div>

      <!-- Security Tab -->
      <div v-else-if="activeTab === 'security'" class="p-6 space-y-6">
        <div class="max-w-2xl space-y-6">
          <!-- Password Policy Section -->
          <div>
            <h3 class="text-sm font-medium text-slate-700 mb-4">密码策略</h3>

            <!-- Complexity Score -->
            <div class="p-4 bg-slate-50 rounded-lg mb-4">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium text-slate-700">密码强度等级</span>
                <span :class="complexityLevel.color" class="font-bold">{{ complexityLevel.label }}</span>
              </div>
              <div class="w-full bg-slate-200 rounded-full h-2">
                <div
                  class="h-2 rounded-full transition-all duration-300"
                  :class="passwordComplexityScore >= 5 ? 'bg-success' : passwordComplexityScore >= 3 ? 'bg-yellow-500' : 'bg-error'"
                  :style="{ width: `${(passwordComplexityScore / 6) * 100}%` }"
                ></div>
              </div>
              <p class="text-xs text-slate-500 mt-2">根据配置的密码要求计算强度等级</p>
            </div>

            <!-- Minimum Length -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-slate-700 mb-1">最小密码长度</label>
              <div class="flex items-center gap-4">
                <input
                  v-model.number="form.password_min_length"
                  type="range"
                  min="6"
                  max="32"
                  class="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-primary"
                />
                <span class="w-12 text-center font-bold text-primary text-lg">{{ form.password_min_length }}</span>
              </div>
              <p class="text-xs text-slate-500 mt-1">建议不少于8个字符</p>
            </div>

            <!-- Character Requirements -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-3">字符要求</label>
              <div class="space-y-3">
                <label class="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors">
                  <input
                    v-model="form.password_require_uppercase"
                    type="checkbox"
                    class="w-4 h-4 text-primary rounded focus:ring-primary"
                  />
                  <div>
                    <span class="font-medium text-slate-700">大写字母</span>
                    <span class="ml-2 px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded font-mono">A-Z</span>
                  </div>
                </label>

                <label class="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors">
                  <input
                    v-model="form.password_require_lowercase"
                    type="checkbox"
                    class="w-4 h-4 text-primary rounded focus:ring-primary"
                  />
                  <div>
                    <span class="font-medium text-slate-700">小写字母</span>
                    <span class="ml-2 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded font-mono">a-z</span>
                  </div>
                </label>

                <label class="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors">
                  <input
                    v-model="form.password_require_digit"
                    type="checkbox"
                    class="w-4 h-4 text-primary rounded focus:ring-primary"
                  />
                  <div>
                    <span class="font-medium text-slate-700">数字</span>
                    <span class="ml-2 px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded font-mono">0-9</span>
                  </div>
                </label>

                <label class="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors">
                  <input
                    v-model="form.password_require_special"
                    type="checkbox"
                    class="w-4 h-4 text-primary rounded focus:ring-primary"
                  />
                  <div>
                    <span class="font-medium text-slate-700">特殊字符</span>
                    <span class="ml-2 px-2 py-0.5 bg-orange-100 text-orange-700 text-xs rounded font-mono">!@#$%^&*</span>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <!-- Login Security Section -->
          <div>
            <h3 class="text-sm font-medium text-slate-700 mb-4">登录安全</h3>

            <!-- Login Attempts -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-slate-700 mb-1">最大登录尝试次数</label>
              <div class="flex items-center gap-4">
                <input
                  v-model.number="form.max_login_attempts"
                  type="number"
                  min="1"
                  max="10"
                  class="input-field w-32"
                />
                <span class="text-slate-600">次</span>
              </div>
              <p class="text-xs text-slate-500 mt-1">超过此次数后账户将被临时锁定</p>
            </div>

            <!-- Lockout Duration -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-slate-700 mb-1">锁定时间</label>
              <div class="flex items-center gap-4">
                <input
                  v-model.number="form.lockout_duration"
                  type="number"
                  min="1"
                  max="1440"
                  class="input-field w-32"
                />
                <span class="text-slate-600">分钟</span>
              </div>
              <p class="text-xs text-slate-500 mt-1">账户被锁定的持续时间，超过后自动解锁 (1-1440分钟)</p>
            </div>

            <!-- Session Timeout -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">会话超时时间</label>
              <div class="flex items-center gap-3">
                <input
                  v-model.number="form.session_timeout"
                  type="number"
                  min="1"
                  max="10080"
                  class="input-field w-32"
                />
                <span class="text-slate-600">分钟</span>
              </div>
              <p class="text-xs text-slate-500 mt-1">用户登录后，无操作自动登出的时间 (1-10080分钟)</p>
            </div>

            <!-- OTP Issuer Name -->
            <div class="border-t border-slate-100 pt-4 mt-4">
              <h3 class="text-sm font-medium text-slate-700 mb-4">MFA 设置</h3>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">OTP 验证器名称</label>
                <input
                  v-model="form.otp_issuer_name"
                  type="text"
                  class="input-field w-64"
                  placeholder="CMDB"
                />
                <p class="text-xs text-slate-500 mt-1">用户扫码绑定 MFA 时，验证器应用中显示的服务名称</p>
              </div>
            </div>
          </div>

          <!-- Security Info -->
          <div class="p-4 bg-blue-50 rounded-lg">
            <div class="flex items-start gap-3">
              <InfoCircleOutlined class="text-blue-600" />
              <div class="text-sm text-blue-800">
                <p class="font-medium">安全提示</p>
                <ul class="mt-2 space-y-1 list-disc list-inside text-blue-700">
                  <li>建议将最大登录尝试次数设置为 3-5 次</li>
                  <li>账户锁定时间建议 15-30 分钟，过短则无法有效防止暴力破解</li>
                  <li>会话超时时间不宜过长，建议 30-120 分钟</li>
                  <li>强密码策略可有效防止暴力破解攻击</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Encryption Info -->
          <div class="p-4 bg-slate-50 rounded-lg">
            <h3 class="text-sm font-medium text-slate-700 mb-3">加密设置</h3>
            <div class="space-y-2 text-sm">
              <div class="flex items-center justify-between py-2 border-b border-slate-200">
                <span class="text-slate-600">凭证加密算法</span>
                <span class="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded font-medium">Fernet (AES-128)</span>
              </div>
              <div class="flex items-center justify-between py-2 border-b border-slate-200">
                <span class="text-slate-600">密码哈希算法</span>
                <span class="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded font-medium">bcrypt</span>
              </div>
              <div class="flex items-center justify-between py-2">
                <span class="text-slate-600">JWT 签名算法</span>
                <span class="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded font-medium">HS256</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-3 pt-4 border-t border-slate-100">
          <button @click="saveSettings" :disabled="saving" class="btn-primary flex items-center gap-2">
            <LoadingOutlined v-if="saving" class="animate-spin text-lg" />
            <SaveOutlined v-else class="text-lg" />
            {{ saving ? '保存中...' : '保存设置' }}
          </button>
          <button @click="resetToDefaults" class="btn-secondary">恢复默认</button>
        </div>
      </div>

      <!-- Branding Tab -->
      <div v-else-if="activeTab === 'branding'" class="p-6 space-y-6">
        <div class="max-w-2xl space-y-6">
          <!-- Login Subtitle -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">登录页副标题</label>
            <input
              v-model="form.login_subtitle"
              type="text"
              class="input-field"
              placeholder="企业资产配置管理平台"
            />
            <p class="text-xs text-slate-500 mt-1">显示在登录页 Logo 下方的描述文字</p>
          </div>

          <!-- Logo Image -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Logo 图片</label>
            <div class="flex items-center gap-4">
              <div class="w-20 h-20 rounded-lg border-2 border-dashed border-slate-300 flex items-center justify-center overflow-hidden bg-slate-50">
                <img
                  v-if="form.logo_image"
                  :src="form.logo_image"
                  class="w-full h-full object-contain"
                  alt="Logo preview"
                />
                <DatabaseOutlined v-else class="text-slate-400 text-2xl" />
              </div>
              <div class="flex-1 space-y-2">
                <label
                  class="flex items-center justify-center gap-1 px-4 py-2 border border-slate-300 rounded-lg cursor-pointer hover:bg-slate-50 transition-colors text-sm"
                >
                  <LoadingOutlined v-if="logoUploading" class="animate-spin" />
                  <span v-else>选择文件</span>
                  <input
                    ref="logoInput"
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
                    class="hidden"
                    @change="($event: any) => $event.target.files[0] && handleLogoUpload($event.target.files[0])"
                  />
                </label>
                <p v-if="form.logo_image" class="text-xs text-slate-500">
                  已上传
                  <button @click="clearLogo" class="text-error hover:underline ml-1">移除</button>
                </p>
                <p v-else class="text-xs text-slate-500">支持 PNG、JPG、GIF、WebP、SVG，最大 10MB</p>
              </div>
            </div>
          </div>

          <!-- Background Image -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">登录页背景图片</label>
            <div class="flex items-center gap-4">
              <div class="w-32 h-20 rounded-lg border-2 border-dashed border-slate-300 overflow-hidden bg-slate-50 relative">
                <img
                  v-if="form.login_background_image"
                  :src="form.login_background_image"
                  class="w-full h-full object-cover"
                  alt="Background preview"
                />
                <div v-else class="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary to-primary-container">
                  <span class="text-white/60 text-xs">无图片</span>
                </div>
              </div>
              <div class="flex-1 space-y-2">
                <label
                  class="flex items-center justify-center gap-1 px-4 py-2 border border-slate-300 rounded-lg cursor-pointer hover:bg-slate-50 transition-colors text-sm"
                >
                  <LoadingOutlined v-if="bgUploading" class="animate-spin" />
                  <span v-else>选择文件</span>
                  <input
                    ref="bgInput"
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    class="hidden"
                    @change="($event: any) => $event.target.files[0] && handleBgUpload($event.target.files[0])"
                  />
                </label>
                <p v-if="form.login_background_image" class="text-xs text-slate-500">
                  已上传
                  <button @click="clearBackground" class="text-error hover:underline ml-1">移除</button>
                </p>
                <p v-else class="text-xs text-slate-500">支持 PNG、JPG、GIF、WebP，最大 10MB</p>
              </div>
            </div>
          </div>

          <!-- Preview -->
          <div class="p-4 bg-slate-50 rounded-lg">
            <p class="text-sm font-medium text-slate-700 mb-2">预览</p>
            <div
              class="rounded-lg overflow-hidden h-32 flex items-center justify-center relative"
              :class="form.login_background_image ? '' : 'bg-gradient-to-br from-primary to-primary-container'"
              :style="form.login_background_image ? { backgroundImage: `url(${form.login_background_image})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}"
            >
              <div v-if="form.login_background_image" class="absolute inset-0 bg-black/30" />
              <div class="relative z-10 flex flex-col items-center">
                <div class="bg-white/10 backdrop-blur-xl rounded-full p-2 mb-2">
                  <img
                    v-if="form.logo_image"
                    :src="form.logo_image"
                    class="w-8 h-8 object-contain"
                    alt="Logo"
                  />
                  <DatabaseOutlined v-else class="text-white text-xl" />
                </div>
                <span v-if="form.site_title" class="text-white font-bold text-sm">{{ form.site_title }}</span>
                <span v-if="form.login_subtitle" class="text-white/80 text-xs">{{ form.login_subtitle }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-3 pt-4 border-t border-slate-100">
          <button @click="saveSettings" :disabled="saving" class="btn-primary flex items-center gap-2">
            <LoadingOutlined v-if="saving" class="animate-spin text-lg" />
            <SaveOutlined v-else class="text-lg" />
            {{ saving ? '保存中...' : '保存设置' }}
          </button>
          <button @click="resetToDefaults" class="btn-secondary">恢复默认</button>
        </div>
      </div>

      <!-- Email Tab -->
      <div v-else-if="activeTab === 'email'" class="p-6 space-y-6">
        <div class="max-w-2xl space-y-6">
          <div>
            <h3 class="text-sm font-medium text-slate-700 mb-4">SMTP 服务器</h3>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">SMTP 服务器地址</label>
                <input v-model="form.smtp_host" type="text" class="input-field" placeholder="smtp.example.com" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">端口</label>
                <input v-model.number="form.smtp_port" type="number" min="1" max="65535" class="input-field" placeholder="465" />
              </div>
            </div>
            <label class="flex items-center gap-2 cursor-pointer mt-4">
              <input v-model="form.smtp_use_ssl" type="checkbox" class="w-4 h-4 text-primary rounded focus:ring-primary" />
              <span class="text-sm text-slate-700">开启 SSL 安全连接</span>
            </label>
          </div>

          <div class="border-t border-slate-100 pt-6">
            <h3 class="text-sm font-medium text-slate-700 mb-4">认证信息</h3>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">SMTP 用户名</label>
                <input v-model="form.smtp_username" type="text" class="input-field" autocomplete="username" placeholder="SMTP 用户名" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">SMTP 密码</label>
                <input v-model="form.smtp_password" type="password" class="input-field" autocomplete="new-password" placeholder="留空则清除，保持 ******** 则不修改" />
              </div>
            </div>
          </div>

          <div class="border-t border-slate-100 pt-6">
            <h3 class="text-sm font-medium text-slate-700 mb-4">发件人</h3>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">发件人邮箱</label>
                <input v-model="form.smtp_from_email" type="email" class="input-field" placeholder="noreply@example.com" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">发件人名称</label>
                <input v-model="form.smtp_from_name" type="text" class="input-field" placeholder="CMDB" />
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-3 pt-4 border-t border-slate-100">
          <button @click="saveSettings" :disabled="saving" class="btn-primary flex items-center gap-2">
            <LoadingOutlined v-if="saving" class="animate-spin text-lg" />
            <SaveOutlined v-else class="text-lg" />
            {{ saving ? '保存中...' : '保存设置' }}
          </button>
          <button @click="resetToDefaults" class="btn-secondary">恢复默认</button>
        </div>
      </div>
    </div>
  </div>
</template>
