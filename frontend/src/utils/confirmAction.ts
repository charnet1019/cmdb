import { Modal, message } from 'ant-design-vue'

interface ConfirmActionOptions {
  title: string
  content: string
  okText?: string
  danger?: boolean
  successMessage?: string
  errorMessage?: string
  formatError?: (error: any) => string
  onOk: () => Promise<void>
}

// Shared confirm-dialog + try/catch/message wrapper for destructive or
// state-changing actions (delete, reset, force-logout, status change, etc).
export function confirmAction(options: ConfirmActionOptions) {
  Modal.confirm({
    title: options.title,
    content: options.content,
    okText: options.okText ?? '确定',
    okType: options.danger === false ? undefined : 'danger',
    cancelText: '取消',
    centered: true,
    onOk: async () => {
      try {
        await options.onOk()
        if (options.successMessage) message.success(options.successMessage)
      } catch (e: any) {
        const fallback = e?.response?.data?.detail || options.errorMessage || '操作失败'
        message.error(options.formatError ? options.formatError(e) : fallback)
      }
    },
  })
}
