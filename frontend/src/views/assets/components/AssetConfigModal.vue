<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  getAssetConfig,
  getAssetConfigContent,
  getAssetConfigVersions,
  getAssetConfigVersionContent,
  uploadAssetConfig,
  saveAssetConfigContent,
  rollbackAssetConfig,
  deleteAssetConfig,
} from '@/api/assets'
import type { Asset, AssetConfigFileSummary, AssetConfigVersion } from '@/types'

const props = defineProps<{
  open: boolean
  asset: Asset | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const versionsLoading = ref(false)
const meta = ref<AssetConfigFileSummary | null>(null)
const versions = ref<AssetConfigVersion[]>([])
const filename = ref('')
const originalContent = ref('')
const editorContent = ref('')
const changeSummary = ref('')
const showDiff = ref(false)
const diffTitle = ref('保存前对比')
const editorEl = ref<HTMLElement | null>(null)
const diffEl = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

let monacoApi: any = null
let editor: any = null
let diffEditor: any = null

async function loadMonaco() {
  if (!monacoApi) {
    monacoApi = await import('monaco-editor')
  }
  return monacoApi
}

function disposeEditor() {
  if (editor) {
    editor.dispose()
    editor = null
  }
}

function disposeDiffEditor() {
  if (diffEditor) {
    diffEditor.dispose()
    diffEditor = null
  }
}

async function mountEditor(readOnly: boolean) {
  await nextTick()
  if (!editorEl.value) return
  const monaco = await loadMonaco()
  disposeEditor()
  editor = monaco.editor.create(editorEl.value, {
    value: editorContent.value,
    language: 'plaintext',
    readOnly,
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 13,
    wordWrap: 'off',
    scrollBeyondLastLine: false,
  })
  editor.onDidChangeModelContent(() => {
    editorContent.value = editor.getValue()
  })
}

async function mountDiff(original: string, modified: string) {
  await nextTick()
  if (!diffEl.value) return
  const monaco = await loadMonaco()
  disposeDiffEditor()
  diffEditor = monaco.editor.createDiffEditor(diffEl.value, {
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 13,
    readOnly: true,
    renderSideBySide: true,
  })
  diffEditor.setModel({
    original: monaco.editor.createModel(original, 'plaintext'),
    modified: monaco.editor.createModel(modified, 'plaintext'),
  })
}

async function refreshVersions() {
  if (!props.asset || !meta.value?.filename || !meta.value.can_view) {
    versions.value = []
    return
  }
  versionsLoading.value = true
  try {
    versions.value = await getAssetConfigVersions(props.asset.id)
  } finally {
    versionsLoading.value = false
  }
}

async function loadConfig() {
  if (!props.asset) return
  loading.value = true
  try {
    meta.value = await getAssetConfig(props.asset.id)
    filename.value = meta.value.filename || ''
    originalContent.value = ''
    editorContent.value = ''

    if (meta.value.filename && meta.value.can_view) {
      const content = await getAssetConfigContent(props.asset.id)
      filename.value = content.filename || filename.value
      originalContent.value = content.content
      editorContent.value = content.content
    }
    await refreshVersions()
    await mountEditor(!(meta.value?.can_edit))
  } catch (error: any) {
    message.error(error.response?.data?.detail || '加载配置文件失败')
  } finally {
    loading.value = false
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !props.asset) return
  uploading.value = true
  try {
    meta.value = await uploadAssetConfig(props.asset.id, file)
    message.success('配置文件已上传')
    await loadConfig()
    emit('saved')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function previewSaveDiff() {
  if (!props.asset || !meta.value?.can_edit) return
  if (!filename.value.trim()) {
    message.warning('请输入配置文件名')
    return
  }
  if (!filename.value.endsWith('.cfg') && !filename.value.endsWith('.conf')) {
    message.warning('文件名必须以 .cfg 或 .conf 结尾')
    return
  }
  showDiff.value = true
  diffTitle.value = '保存前对比'
  await mountDiff(originalContent.value, editorContent.value)
}

async function confirmSave() {
  if (!props.asset) return
  saving.value = true
  try {
    meta.value = await saveAssetConfigContent(props.asset.id, {
      filename: filename.value,
      content: editorContent.value,
      change_summary: changeSummary.value,
    })
    showDiff.value = false
    changeSummary.value = ''
    message.success('配置已保存')
    await loadConfig()
    emit('saved')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function compareVersion(version: AssetConfigVersion) {
  if (!props.asset) return
  const versionContent = await getAssetConfigVersionContent(props.asset.id, version.id)
  showDiff.value = true
  diffTitle.value = `当前版本 / v${version.version_no}`
  await mountDiff(originalContent.value, versionContent.content)
}

async function rollbackVersion(version: AssetConfigVersion) {
  if (!props.asset) return
  if (!window.confirm(`确认回滚到版本 v${version.version_no}？回滚会生成一个新版本。`)) return
  saving.value = true
  try {
    meta.value = await rollbackAssetConfig(props.asset.id, version.id, `回滚到版本 ${version.version_no}`)
    message.success('已回滚配置')
    await loadConfig()
    emit('saved')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '回滚失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!props.asset) return
  if (!window.confirm('确认删除当前配置文件及所有版本？')) return
  saving.value = true
  try {
    await deleteAssetConfig(props.asset.id)
    message.success('配置文件已删除')
    await loadConfig()
    emit('saved')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '删除失败')
  } finally {
    saving.value = false
  }
}

function close() {
  showDiff.value = false
  emit('close')
}

watch(() => props.open, async (open) => {
  if (open) {
    await loadConfig()
  } else {
    disposeEditor()
    disposeDiffEditor()
  }
})

onBeforeUnmount(() => {
  disposeEditor()
  disposeDiffEditor()
})
</script>

<template>
  <div v-if="open && asset" class="fixed inset-0 z-[70] flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-slate-900/60" @click="close"></div>
    <div class="relative bg-white rounded-lg shadow-xl w-full max-w-6xl max-h-[92vh] flex flex-col overflow-hidden">
      <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h3 class="text-base font-semibold text-slate-900">配置文件 - {{ asset.name }}</h3>
          <p class="text-xs text-slate-500 mt-1">
            {{ meta?.filename || '未上传配置文件' }}
            <span v-if="meta?.version_no" class="ml-2">v{{ meta.version_no }}</span>
          </p>
        </div>
        <button class="text-slate-400 hover:text-slate-700" @click="close">关闭</button>
      </div>

      <div class="flex-1 overflow-hidden grid grid-cols-[1fr_280px] min-h-[560px]">
        <div class="p-4 flex flex-col min-w-0">
          <div class="mb-3 flex items-center gap-2">
            <input
              v-model="filename"
              :disabled="!meta?.can_edit"
              class="input-field max-w-sm"
              placeholder="例如 running-config.cfg"
            />
            <button v-if="meta?.can_edit" class="btn-secondary" :disabled="uploading" @click="openFilePicker">
              {{ meta?.filename ? '上传替换' : '上传配置' }}
            </button>
            <button v-if="meta?.can_edit" class="btn-primary" :disabled="saving" @click="previewSaveDiff">保存</button>
            <button v-if="meta?.can_edit && meta?.filename" class="border border-red-300 text-red-600 px-3 py-1.5 rounded text-sm" @click="handleDelete">删除</button>
            <input ref="fileInput" type="file" accept=".cfg,.conf" class="hidden" @change="handleUpload" />
          </div>

          <div v-if="loading" class="flex-1 flex items-center justify-center text-slate-500">加载中...</div>
          <button
            v-else-if="!meta?.filename && meta?.can_edit"
            class="flex-1 border border-dashed border-slate-300 rounded-lg text-slate-400 hover:text-primary hover:border-primary"
            @click="openFilePicker"
          >
            点击上传 .cfg 或 .conf 配置文件
          </button>
          <div v-show="!loading && (meta?.filename || !meta?.can_edit)" ref="editorEl" class="flex-1 border border-slate-200 rounded"></div>
        </div>

        <aside class="border-l border-slate-200 p-4 overflow-y-auto bg-slate-50">
          <div class="text-sm font-semibold text-slate-700 mb-3">版本历史</div>
          <div v-if="versionsLoading" class="text-sm text-slate-500">加载中...</div>
          <div v-else-if="versions.length === 0" class="text-sm text-slate-400">暂无版本</div>
          <div v-else class="space-y-2">
            <div v-for="version in versions" :key="version.id" class="bg-white border border-slate-200 rounded p-3">
              <div class="flex items-center justify-between gap-2">
                <span class="font-semibold text-sm text-slate-800">v{{ version.version_no }}</span>
                <span v-if="version.is_current" class="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700">当前</span>
              </div>
              <div class="text-xs text-slate-500 mt-1 truncate" :title="version.filename">{{ version.filename }}</div>
              <div class="text-xs text-slate-400 mt-1">{{ version.created_by_username || '-' }} · {{ version.created_at ? new Date(version.created_at).toLocaleString('zh-CN') : '-' }}</div>
              <div v-if="version.change_summary" class="text-xs text-slate-500 mt-1">{{ version.change_summary }}</div>
              <div class="flex gap-2 mt-2">
                <button class="text-xs text-primary hover:underline" @click="compareVersion(version)">对比</button>
                <button v-if="meta?.can_edit && !version.is_current" class="text-xs text-slate-600 hover:underline" @click="rollbackVersion(version)">回滚</button>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>

    <div v-if="showDiff" class="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/70" @click="showDiff = false"></div>
      <div class="relative bg-white rounded-lg shadow-xl w-full max-w-6xl h-[82vh] flex flex-col overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 class="text-base font-semibold text-slate-900">{{ diffTitle }}</h3>
          <button class="text-slate-400 hover:text-slate-700" @click="showDiff = false">关闭</button>
        </div>
        <div ref="diffEl" class="flex-1"></div>
        <div v-if="diffTitle === '保存前对比'" class="px-5 py-3 border-t border-slate-200 flex items-center gap-3">
          <input v-model="changeSummary" class="input-field flex-1" placeholder="变更说明（可选）" />
          <button class="btn-secondary" @click="showDiff = false">取消</button>
          <button class="btn-primary" :disabled="saving" @click="confirmSave">确认保存</button>
        </div>
      </div>
    </div>
  </div>
</template>
