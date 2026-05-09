<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  CloseOutlined,
  DownloadOutlined,
  UploadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons-vue'
import { downloadImportTemplate, importAssets, type ImportResult } from '@/api/assets'
import * as XLSX from 'xlsx'

const props = defineProps<{
  visible: boolean
  category: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

// Import mode state
const importMode = ref<'create' | 'update'>('create')

// File handling state
const selectedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const importResult = ref<ImportResult | null>(null)

// Modal title based on mode
const modalTitle = computed(() =>
  importMode.value === 'create' ? '导入创建' : '导入更新'
)

// Reset state when modal opens/closes
watch(() => props.visible, (visible) => {
  if (visible) {
    selectedFile.value = null
    importResult.value = null
    importing.value = false
    if (fileInputRef.value) {
      fileInputRef.value.value = ''
    }
  }
})

// Handle file selection
async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]

  if (file) {
    // Validate file type
    if (!file.name.endsWith('.xlsx')) {
      message.error('请选择xlsx格式的文件')
      target.value = ''
      return
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      message.error('文件大小不能超过10MB')
      target.value = ''
      return
    }

    // Validate template type matches import mode
    const isValid = await validateTemplateType(file)
    if (!isValid) {
      target.value = ''
      return
    }

    selectedFile.value = file
    importResult.value = null
  }
}

// Validate template type matches import mode
async function validateTemplateType(file: File): Promise<boolean> {
  try {
    const arrayBuffer = await file.arrayBuffer()
    const workbook = XLSX.read(arrayBuffer, { type: 'array' })
    const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
    const headers = XLSX.utils.sheet_to_json(firstSheet, { header: 1, defval: '' })[0] || []

    const headerLabels = (headers as any[]).map(h => String(h).trim())
    const hasIdField = headerLabels.some((label: string) => label.includes('ID') || label === '*ID')

    if (importMode.value === 'create' && hasIdField) {
      message.error('检测到更新模板（包含 ID 字段），请切换到"更新"模式或使用创建模板')
      return false
    }

    if (importMode.value === 'update' && !hasIdField) {
      message.error('检测到创建模板（缺少 ID 字段），请切换到"创建"模式或使用更新模板')
      return false
    }

    return true
  } catch (error) {
    console.error('Template validation error:', error)
    // If validation fails, allow user to proceed (backend will validate)
    return true
  }
}

// Trigger file input click
function triggerFileInput() {
  fileInputRef.value?.click()
}

// Clear selected file
function clearFile() {
  selectedFile.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

// Download template
async function handleDownloadTemplate() {
  try {
    await downloadImportTemplate(props.category, importMode.value)
    message.success('模板下载成功')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '模板下载失败')
  }
}

// Execute import
async function handleImport() {
  if (!selectedFile.value) {
    message.warning('请先选择要导入的文件')
    return
  }

  importing.value = true
  try {
    const result = await importAssets(props.category, importMode.value, selectedFile.value)
    importResult.value = result

    if (result.success_count > 0) {
      message.success(`成功导入 ${result.success_count} 条记录`)
      emit('success')
    }

    if (result.failed_count > 0) {
      message.warning(`${result.failed_count} 条记录导入失败`)
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

// Close modal
function close() {
  emit('update:visible', false)
}

// Format error message
function formatError(error: any): string {
  if (error.errors && Array.isArray(error.errors)) {
    return `第${error.row}行: ${error.errors.join('; ')}`
  }
  if (error.error) {
    return `ID ${error.id || error.name}: ${error.error}`
  }
  return String(error)
}
</script>

<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="close"></div>
    <div class="relative bg-white w-full max-w-lg rounded-xl shadow-2xl">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
        <h2 class="text-lg font-bold text-slate-900">{{ modalTitle }}</h2>
        <button @click="close" class="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
          <CloseOutlined class="text-slate-400" />
        </button>
      </div>

      <!-- Content -->
      <div class="p-6 space-y-5">
        <!-- Row 1: Mode selection -->
        <div class="flex items-center gap-6">
          <span class="text-sm font-medium text-slate-700">导入</span>
          <div class="flex items-center gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                v-model="importMode"
                value="create"
                class="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
              />
              <span class="text-sm text-slate-600">创建</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                v-model="importMode"
                value="update"
                class="w-4 h-4 text-primary border-gray-300 focus:ring-primary"
              />
              <span class="text-sm text-slate-600">更新</span>
            </label>
          </div>
        </div>

        <!-- Row 2: Download template -->
        <div>
          <button
            @click="handleDownloadTemplate"
            class="flex items-center gap-2 px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            <DownloadOutlined class="text-slate-500" />
            <span class="text-sm text-slate-600">
              下载{{ importMode === 'create' ? '创建' : '更新' }}模板
            </span>
          </button>
          <p class="mt-2 text-xs text-slate-400">
            {{ importMode === 'create'
              ? '创建模板中name字段为必填项(标记*)，其他字段可选'
              : '更新模板中ID字段为必填项(标记*)，其他字段可选，仅更新非空字段'
            }}
          </p>
        </div>

        <!-- Row 3: File upload -->
        <div>
          <input
            ref="fileInputRef"
            type="file"
            accept=".xlsx"
            class="hidden"
            @change="handleFileSelect"
          />

          <!-- File selection area -->
          <div
            v-if="!selectedFile"
            @click="triggerFileInput"
            class="border-2 border-dashed border-slate-200 rounded-lg p-6 text-center cursor-pointer hover:border-primary hover:bg-slate-50 transition-colors"
          >
            <UploadOutlined class="text-3xl text-slate-400 mb-2" />
            <p class="text-sm text-slate-600">点击选择xlsx文件</p>
            <p class="text-xs text-slate-400 mt-1">支持.xlsx格式，最大10MB</p>
          </div>

          <!-- Selected file display -->
          <div
            v-else
            class="border border-slate-200 rounded-lg p-4 flex items-center justify-between"
          >
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <CheckCircleOutlined class="text-green-600" />
              </div>
              <div>
                <p class="text-sm font-medium text-slate-700">{{ selectedFile.name }}</p>
                <p class="text-xs text-slate-400">{{ (selectedFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </div>
            <button
              @click="clearFile"
              class="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <CloseOutlined class="text-slate-400" />
            </button>
          </div>
        </div>

        <!-- Row 4: Import result -->
        <div v-if="importResult" class="border border-slate-200 rounded-lg p-4">
          <div class="flex items-center gap-4 mb-3">
            <div class="flex items-center gap-2">
              <CheckCircleOutlined class="text-green-600" />
              <span class="text-sm text-slate-600">成功: {{ importResult.success_count }}</span>
            </div>
            <div v-if="importResult.failed_count > 0" class="flex items-center gap-2">
              <CloseCircleOutlined class="text-red-500" />
              <span class="text-sm text-slate-600">失败: {{ importResult.failed_count }}</span>
            </div>
          </div>

          <!-- Error details -->
          <div v-if="importResult.errors.length > 0" class="mt-3 space-y-2">
            <div class="text-xs font-medium text-slate-500 mb-2">错误详情:</div>
            <div
              v-for="(error, index) in importResult.errors.slice(0, 10)"
              :key="index"
              class="text-xs text-red-600 bg-red-50 px-3 py-2 rounded"
            >
              {{ formatError(error) }}
            </div>
            <div v-if="importResult.errors.length > 10" class="text-xs text-slate-400">
              ... 还有 {{ importResult.errors.length - 10 }} 条错误
            </div>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="flex justify-end gap-3 pt-4 border-t border-slate-100">
          <button
            @click="close"
            class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
          >
            关闭
          </button>
          <button
            @click="handleImport"
            :disabled="!selectedFile || importing"
            class="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ importing ? '导入中...' : '开始导入' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
