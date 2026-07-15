// Shared client-side file validation helpers.
export const ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']

export function validateImageFile(file: File, maxSizeMB = 10): string | null {
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
    return '仅支持 PNG、JPG、GIF、WebP 格式'
  }
  if (file.size > maxSizeMB * 1024 * 1024) {
    return `文件大小不能超过 ${maxSizeMB}MB`
  }
  return null
}

export function validateFileExtension(file: File, allowedExtensions: string[]): string | null {
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!allowedExtensions.includes(ext)) {
    return `仅支持 ${allowedExtensions.join('、')} 格式`
  }
  return null
}

export function validateFileSize(file: File, maxSizeMB: number): string | null {
  if (file.size > maxSizeMB * 1024 * 1024) {
    return `文件大小不能超过 ${maxSizeMB}MB`
  }
  return null
}
