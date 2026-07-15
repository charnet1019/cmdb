import { ref, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import { uploadImage, deleteImage } from '@/api/settings'
import { validateImageFile } from '@/utils/fileValidation'

/**
 * Manages a single settings-page image field (logo, login background, etc):
 * upload, clear, and deferred deletion of the previously-saved file once the
 * new value is actually persisted (or reverted) via saveSettings/reset.
 */
export function useImageUploadField(value: Ref<string | null>, successMessage: string) {
  const uploading = ref(false)
  const inputRef = ref<HTMLInputElement | null>(null)
  const originalValue = ref<string | null>(null)
  const pendingDeletes = new Set<string>()

  function resetFileInput() {
    if (inputRef.value) inputRef.value.value = ''
  }

  function uploadedFilename(url: string | null): string | null {
    if (!url || !url.startsWith('/uploads/')) return null
    return url.split('/').pop() || null
  }

  function queueOrDeletePrevious(previous: string | null) {
    const filename = uploadedFilename(previous)
    if (!filename) return
    if (previous === originalValue.value) {
      pendingDeletes.add(filename)
    } else {
      void deleteImage(filename).catch(() => {})
    }
  }

  async function handleUpload(file: File) {
    const validationError = validateImageFile(file)
    if (validationError) {
      message.warning(validationError)
      return
    }
    uploading.value = true
    try {
      const previous = value.value
      const result = await uploadImage(file)
      value.value = result.url
      if (previous && previous !== result.url) {
        queueOrDeletePrevious(previous)
      }
      message.success(successMessage)
    } catch (error: any) {
      message.error(error.response?.data?.detail || '上传失败')
    } finally {
      uploading.value = false
      resetFileInput()
    }
  }

  async function clear() {
    queueOrDeletePrevious(value.value)
    value.value = null
    resetFileInput()
  }

  // Call after fetching settings, so subsequent clear/upload can tell whether
  // the current value was already persisted (needs deferred delete) or was
  // uploaded-but-unsaved in this session (delete immediately).
  function markSaved() {
    originalValue.value = value.value
    pendingDeletes.clear()
  }

  // Call after a successful save — deletes files that were replaced/cleared
  // and are now confirmed gone from the saved settings.
  async function flushPendingDeletes() {
    const filenames = Array.from(pendingDeletes)
    pendingDeletes.clear()
    await Promise.all(filenames.map(filename => deleteImage(filename).catch(() => {})))
  }

  return {
    uploading,
    inputRef,
    handleUpload,
    clear,
    markSaved,
    flushPendingDeletes,
  }
}
