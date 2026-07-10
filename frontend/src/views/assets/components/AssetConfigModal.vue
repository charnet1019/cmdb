<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import {
  getAssetConfig,
  getAssetConfigContent,
  getAssetConfigVersions,
  getAssetConfigVersionContent,
  downloadAssetConfig,
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
const downloading = ref(false)
const versionsLoading = ref(false)
const meta = ref<AssetConfigFileSummary | null>(null)
const versions = ref<AssetConfigVersion[]>([])
const filename = ref('')
const originalContent = ref('')
const editorContent = ref('')
const changeSummary = ref('')
const showDiff = ref(false)
const diffTitle = ref('保存前对比')
const diffOriginalTitle = ref('当前版本')
const diffModifiedTitle = ref('编辑内容')
const rollbackTarget = ref<AssetConfigVersion | null>(null)
const showRollbackConfirm = ref(false)
const editorEl = ref<HTMLElement | null>(null)
const diffEl = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

let monacoApi: any = null
let editor: any = null
let diffEditor: any = null
let diffOriginalModel: any = null
let diffModifiedModel: any = null

function setupMonacoEnvironment() {
  const globalScope = globalThis as typeof globalThis & {
    MonacoEnvironment?: {
      getWorker?: (_moduleId: string, _label: string) => Worker
    }
  }

  if (globalScope.MonacoEnvironment?.getWorker) return

  globalScope.MonacoEnvironment = {
    getWorker() {
      return new EditorWorker()
    },
  }
}

async function loadMonaco() {
  if (!monacoApi) {
    setupMonacoEnvironment()
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
  if (diffOriginalModel) {
    diffOriginalModel.dispose()
    diffOriginalModel = null
  }
  if (diffModifiedModel) {
    diffModifiedModel.dispose()
    diffModifiedModel = null
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
  diffOriginalModel = monaco.editor.createModel(original, 'plaintext')
  diffModifiedModel = monaco.editor.createModel(modified, 'plaintext')
  diffEditor.setModel({
    original: diffOriginalModel,
    modified: diffModifiedModel,
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

async function handleDownloadConfig() {
  if (!props.asset || !meta.value?.filename || !meta.value.can_view) return
  downloading.value = true
  try {
    await downloadAssetConfig(props.asset.id)
  } catch (error: any) {
    let detail = error.response?.data?.detail
    if (!detail && error.response?.data instanceof Blob) {
      try {
        detail = JSON.parse(await error.response.data.text()).detail
      } catch {
        // Use the fallback message below.
      }
    }
    message.error(detail || '下载配置文件失败')
  } finally {
    downloading.value = false
  }
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

function formatVersionTitle(prefix: string, versionNo?: number | null, file?: string | null) {
  const version = versionNo ? ` v${versionNo}` : ''
  const filenamePart = file ? ` - ${file}` : ''
  return `${prefix}${version}${filenamePart}`
}

function closeDiff() {
  showDiff.value = false
  disposeDiffEditor()
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
  diffOriginalTitle.value = formatVersionTitle('当前版本', meta.value?.version_no, meta.value?.filename || filename.value)
  diffModifiedTitle.value = formatVersionTitle('待保存内容', null, filename.value)
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
    closeDiff()
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
  diffTitle.value = '版本对比'
  diffOriginalTitle.value = formatVersionTitle('当前版本', meta.value?.version_no, meta.value?.filename || filename.value)
  diffModifiedTitle.value = formatVersionTitle('历史版本', version.version_no, versionContent.filename || version.filename)
  await mountDiff(originalContent.value, versionContent.content)
}

function openRollbackConfirm(version: AssetConfigVersion) {
  rollbackTarget.value = version
  showRollbackConfirm.value = true
}

function closeRollbackConfirm() {
  if (saving.value) return
  showRollbackConfirm.value = false
  rollbackTarget.value = null
}

async function confirmRollback() {
  if (!props.asset || !rollbackTarget.value) return
  const version = rollbackTarget.value
  saving.value = true
  try {
    meta.value = await rollbackAssetConfig(props.asset.id, version.id, `回滚到版本 ${version.version_no}`)
    message.success('已回滚配置')
    showRollbackConfirm.value = false
    rollbackTarget.value = null
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
  closeDiff()
  showRollbackConfirm.value = false
  rollbackTarget.value = null
  emit('close')
}

watch(() => props.open, async (open) => {
  if (open) {
    await loadConfig()
  } else {
    showRollbackConfirm.value = false
    rollbackTarget.value = null
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
        <div class="min-w-0">
          <h3 class="text-base font-semibold text-slate-900">配置文件 - {{ asset.name }}</h3>
          <p class="text-xs text-slate-500 mt-1 flex items-center gap-2 min-w-0">
            <span class="truncate" :title="meta?.filename || '未上传配置文件'">{{ meta?.filename || '未上传配置文件' }}</span>
            <span v-if="meta?.version_no" class="shrink-0">v{{ meta.version_no }}</span>
            <button
              v-if="meta?.filename && meta?.can_view"
              class="shrink-0 text-primary hover:underline disabled:text-slate-300 disabled:no-underline"
              :disabled="downloading"
              @click="handleDownloadConfig"
            >
              {{ downloading ? '下载中...' : '下载' }}
            </button>
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
                <button v-if="meta?.can_edit && !version.is_current" class="text-xs text-slate-600 hover:underline disabled:text-slate-300 disabled:no-underline" :disabled="saving" @click="openRollbackConfirm(version)">回滚</button>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>


    <div v-if="showRollbackConfirm && rollbackTarget" class="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="closeRollbackConfirm"></div>
      <div class="relative bg-white rounded-lg shadow-xl w-full max-w-md overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 class="text-base font-semibold text-slate-900">确认回滚配置</h3>
          <button class="text-slate-400 hover:text-slate-700 disabled:text-slate-300" :disabled="saving" @click="closeRollbackConfirm">关闭</button>
        </div>
        <div class="px-5 py-4 space-y-3">
          <p class="text-sm text-slate-700">
            确认将当前配置回滚到历史版本 <span class="font-semibold text-slate-900">v{{ rollbackTarget.version_no }}</span>？
          </p>
          <div class="rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 space-y-1">
            <div class="truncate" :title="rollbackTarget.filename">文件：{{ rollbackTarget.filename }}</div>
            <div>创建人：{{ rollbackTarget.created_by_username || '-' }}</div>
            <div>创建时间：{{ rollbackTarget.created_at ? new Date(rollbackTarget.created_at).toLocaleString('zh-CN') : '-' }}</div>
          </div>
          <p class="text-xs text-slate-500">回滚会基于该历史内容生成一个新的当前版本，不会删除历史记录。</p>
        </div>
        <div class="px-5 py-3 border-t border-slate-200 flex items-center justify-end gap-2">
          <button class="btn-secondary" :disabled="saving" @click="closeRollbackConfirm">取消</button>
          <button class="bg-red-600 hover:bg-red-700 disabled:bg-red-300 text-white px-3 py-1.5 rounded text-sm" :disabled="saving" @click="confirmRollback">
            {{ saving ? '回滚中...' : '确认回滚' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showDiff" class="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/70" @click="closeDiff"></div>
      <div class="relative bg-white rounded-lg shadow-xl w-full max-w-6xl h-[82vh] flex flex-col overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 class="text-base font-semibold text-slate-900">{{ diffTitle }}</h3>
          <button class="text-slate-400 hover:text-slate-700" @click="closeDiff">关闭</button>
        </div>
        <div class="grid grid-cols-2 border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
          <div class="min-w-0 px-4 py-2 border-r border-slate-200 truncate" :title="diffOriginalTitle">{{ diffOriginalTitle }}</div>
          <div class="min-w-0 px-4 py-2 truncate" :title="diffModifiedTitle">{{ diffModifiedTitle }}</div>
        </div>
        <div ref="diffEl" class="flex-1"></div>
        <div v-if="diffTitle === '保存前对比'" class="px-5 py-3 border-t border-slate-200 flex items-center gap-3">
          <input v-model="changeSummary" class="input-field flex-1" placeholder="变更说明（可选）" />
          <button class="btn-secondary" @click="closeDiff">取消</button>
          <button class="btn-primary" :disabled="saving" @click="confirmSave">确认保存</button>
        </div>
      </div>
    </div>
  </div>
</template>
