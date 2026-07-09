/**
 * Format datetime to UTC+8 locale string.
 * Backend stores naive UTC datetimes; append Z so JS parses as UTC, then format in Asia/Shanghai.
 */
export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  const iso = dateStr.includes('Z') || dateStr.includes('+') ? dateStr : dateStr + 'Z'
  return new Date(iso).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

/**
 * Format date only (no time) to UTC+8 locale string.
 */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  const iso = dateStr.includes('Z') || dateStr.includes('+') ? dateStr : dateStr + 'Z'
  return new Date(iso).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
}
