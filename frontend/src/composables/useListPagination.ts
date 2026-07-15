import { ref } from 'vue'

/**
 * Shared page/limit state + numbered-pagination helpers for list views
 * (login/operation/password logs, and similar paginated tables).
 */
export function useListPagination(fetchFn: () => void | Promise<void>, initialLimit = 15) {
  const page = ref(1)
  const limit = ref(initialLimit)

  function getPageNumbers(total: number): (number | string)[] {
    const totalPages = Math.ceil(total / limit.value) || 1
    const pages: (number | string)[] = []

    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      pages.push(1)
      if (page.value > 3) pages.push('...')
      const start = Math.max(2, page.value - 1)
      const end = Math.min(totalPages - 1, page.value + 1)
      for (let i = start; i <= end; i++) {
        pages.push(i)
      }
      if (page.value < totalPages - 2) pages.push('...')
      pages.push(totalPages)
    }

    return pages
  }

  function resetPage() {
    page.value = 1
  }

  function handlePageChange(newPage: number) {
    page.value = newPage
    fetchFn()
  }

  function handleLimitChange(newLimit: number) {
    limit.value = newLimit
    page.value = 1
    fetchFn()
  }

  return { page, limit, getPageNumbers, resetPage, handlePageChange, handleLimitChange }
}
