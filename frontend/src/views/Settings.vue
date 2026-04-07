<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import { SettingOutlined, LockOutlined, SafetyCertificateOutlined, LoadingOutlined, SaveOutlined, InfoCircleOutlined } from '@ant-design/icons-vue'
import { getSettings, updateSettings } from '@/api/settings'

// Loading states
const loading = ref(false)
const saving = ref(false)

// Settings data
const settings = ref<Record<string, any>>({})

// Form state
const form = ref({
  // 系统设置
  site_title: 'CMDB',
  session_timeout: 24,
  // 密码策略
  password_min_length: 8,
  password_require_uppercase: true,
  password_require_lowercase: true,
  password_require_digit: true,
  password_require_special: false,
  // 登录设置
  max_login_attempts: 5,
})

// Active tab
const activeTab = ref('system')

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
    if (response.data.password_min_length !== undefined) form.value.password_min_length = response.data.password_min_length
    if (response.data.password_require_uppercase !== undefined) form.value.password_require_uppercase = response.data.password_require_uppercase
    if (response.data.password_require_lowercase !== undefined) form.value.password_require_lowercase = response.data.password_require_lowercase
    if (response.data.password_require_digit !== undefined) form.value.password_require_digit = response.data.password_require_digit
    if (response.data.password_require_special !== undefined) form.value.password_require_special = response.data.password_require_special
    if (response.data.max_login_attempts !== undefined) form.value.max_login_attempts = response.data.max_login_attempts
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
    await updateSettings(form.value)
    message.success('设置已保存')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// Reset to defaults
function resetToDefaults() {
  form.value = {
    site_title: 'CMDB',
    session_timeout: 24,
    password_min_length: 8,
    password_require_uppercase: true,
    password_require_lowercase: true,
    password_require_digit: true,
    password_require_special: false,
    max_login_attempts: 5,
  }
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
            @click="activeTab = 'password'"
            :class="activeTab === 'password' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'"
            class="px-6 py-4 text-sm font-medium border-b-2 -mb-px transition-colors"
          >
            <LockOutlined class="text-lg align-middle mr-1" />
            密码策略
          </button>
          <button
            @click="activeTab = 'security'"
            :class="activeTab === 'security' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'"
            class="px-6 py-4 text-sm font-medium border-b-2 -mb-px transition-colors"
          >
            <SafetyCertificateOutlined class="text-lg align-middle mr-1" />
            登录安全
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

            <!-- Session Timeout -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">会话超时时间</label>
              <div class="flex items-center gap-3">
                <input
                  v-model.number="form.session_timeout"
                  type="number"
                  min="1"
                  max="168"
                  class="input-field w-32"
                />
                <span class="text-slate-600">小时</span>
              </div>
              <p class="text-xs text-slate-500 mt-1">用户登录后，无操作自动登出的时间 (1-168小时)</p>
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

      <!-- Password Policy Tab -->
      <div v-else-if="activeTab === 'password'" class="p-6 space-y-6">
        <div class="max-w-2xl space-y-6">
          <!-- Complexity Score -->
          <div class="p-4 bg-slate-50 rounded-lg">
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
          <div>
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
          <!-- Login Attempts -->
          <div>
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

          <!-- Security Info -->
          <div class="p-4 bg-blue-50 rounded-lg">
            <div class="flex items-start gap-3">
              <InfoCircleOutlined class="text-blue-600" />
              <div class="text-sm text-blue-800">
                <p class="font-medium">安全提示</p>
                <ul class="mt-2 space-y-1 list-disc list-inside text-blue-700">
                  <li>建议将最大登录尝试次数设置为 3-5 次</li>
                  <li>会话超时时间不宜过长，建议 8-24 小时</li>
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
    </div>
  </div>
</template>