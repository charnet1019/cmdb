/**
 * Credentials management composable
 * Handles credential CRUD, decryption, and clipboard operations
 */
import { ref, nextTick } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  decryptCredential,
  deleteCredential
} from '@/api/assets'

export function useCredentials() {
  // Decrypted passwords cache
  const decryptedPasswords = ref<Map<number, string>>(new Map())
  const decryptedFormPasswords = ref<Map<number, string>>(new Map())
  const visibleNewPasswords = ref<Set<number>>(new Set())

  // Form credentials
  const formCredentials = ref<Array<{ username: string; password: string; id?: number }>>([])

  // Editing state
  const editingCredentialField = ref<{ index: number; field: 'username' | 'password' } | null>(null)
  const credentialInputRefs = ref<Map<string, HTMLInputElement>>(new Map())

  // New credential form
  const newCredentialForm = ref({
    username: '',
    password: '',
    credential_type: 'password'
  })

  // Copy to clipboard
  async function copyToClipboard(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      message.success('已复制到剪贴板')
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.left = '-9999px'
      textarea.style.top = '0'
      document.body.appendChild(textarea)
      textarea.focus()
      textarea.select()
      try {
        const success = document.execCommand('copy')
        if (success) {
          message.success('已复制到剪贴板')
        } else {
          message.error('复制失败')
        }
      } catch {
        message.error('复制失败')
      }
      document.body.removeChild(textarea)
    }
  }

  // Copy username
  function copyUsername(username: string) {
    copyToClipboard(username)
  }

  // Copy password - decrypt and copy
  async function copyPassword(credential: { id: number }) {
    const cachedPassword = decryptedPasswords.value.get(credential.id)
    if (cachedPassword) {
      copyToClipboard(cachedPassword)
      return
    }

    try {
      const result = await decryptCredential(credential.id)
      if (result.password) {
        copyToClipboard(result.password)
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '解密失败')
    }
  }

  // View password
  async function viewPassword(credential: { id: number }) {
    if (decryptedPasswords.value.has(credential.id)) {
      decryptedPasswords.value.delete(credential.id)
      return
    }

    try {
      const result = await decryptCredential(credential.id)
      if (result.password) {
        decryptedPasswords.value.set(credential.id, result.password)
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '解密失败')
    }
  }

  // View form credential password
  async function viewFormCredentialPassword(cred: { id?: number; password: string }, index?: number) {
    if (cred.id) {
      if (decryptedFormPasswords.value.has(cred.id)) {
        decryptedFormPasswords.value.delete(cred.id)
        return
      }
      try {
        const result = await decryptCredential(cred.id)
        if (result.password) {
          decryptedFormPasswords.value.set(cred.id, result.password)
        }
      } catch (error: any) {
        message.error(error.response?.data?.detail || '解密失败')
      }
    } else if (index !== undefined) {
      if (visibleNewPasswords.value.has(index)) {
        visibleNewPasswords.value.delete(index)
      } else {
        visibleNewPasswords.value.add(index)
      }
    }
  }

  // Toggle new password visibility
  function toggleNewPasswordVisibility(index: number) {
    if (visibleNewPasswords.value.has(index)) {
      visibleNewPasswords.value.delete(index)
    } else {
      visibleNewPasswords.value.add(index)
    }
  }

  // Add credential to form
  function addCredentialToForm() {
    if (!newCredentialForm.value.username || !newCredentialForm.value.password) {
      message.warning('请输入用户名和密码')
      return
    }
    formCredentials.value.push({
      username: newCredentialForm.value.username,
      password: newCredentialForm.value.password
    })
    newCredentialForm.value = { username: '', password: '', credential_type: 'password' }
  }

  // Remove credential from form
  function removeCredentialFromForm(index: number) {
    formCredentials.value.splice(index, 1)
    editingCredentialField.value = null
  }

  // Field editing
  function startFieldEdit(index: number, field: 'username' | 'password') {
    editingCredentialField.value = { index, field }
    nextTick(() => {
      const key = `${index}-${field}`
      const input = credentialInputRefs.value.get(key)
      if (input) {
        input.focus()
      }
    })
  }

  function stopFieldEdit() {
    setTimeout(() => {
      editingCredentialField.value = null
    }, 100)
  }

  function isFieldEditing(index: number, field: 'username' | 'password'): boolean {
    return editingCredentialField.value?.index === index && editingCredentialField.value?.field === field
  }

  // Delete credential
  async function handleDeleteCredential(credential: { id: number; username?: string }, callback?: () => void) {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除凭证 "${credential.username || '此凭证'}" 吗？删除后无法恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      async onOk() {
        try {
          await deleteCredential(credential.id)
          message.success('凭证已删除')
          callback?.()
        } catch (error) {
          message.error('删除失败')
        }
      }
    })
  }

  // Reset form
  function resetFormCredentials() {
    formCredentials.value = []
    decryptedFormPasswords.value.clear()
    visibleNewPasswords.value.clear()
    newCredentialForm.value = { username: '', password: '', credential_type: 'password' }
  }

  return {
    // State
    decryptedPasswords,
    decryptedFormPasswords,
    visibleNewPasswords,
    formCredentials,
    editingCredentialField,
    credentialInputRefs,
    newCredentialForm,

    // Actions
    copyToClipboard,
    copyUsername,
    copyPassword,
    viewPassword,
    viewFormCredentialPassword,
    toggleNewPasswordVisibility,
    addCredentialToForm,
    removeCredentialFromForm,
    startFieldEdit,
    stopFieldEdit,
    isFieldEditing,
    handleDeleteCredential,
    resetFormCredentials
  }
}