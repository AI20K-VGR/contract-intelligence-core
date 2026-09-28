import { ApiError, requestJson } from './client'

export type ActivityEvent = {
  id: string
  occurred_at: string
  actor_display_name: string | null
  title: string
  detail: string | null
}

export type StorageUsage = {
  used_bytes: number
  quota_bytes: number | null
}

export async function listActivity(options?: {
  limit?: number
  offset?: number
  signal?: AbortSignal
}) {
  const limit = options?.limit ?? 8
  const offset = options?.offset ?? 0
  const { data, meta } = await requestJson<ActivityEvent[]>(
    `/api/v1/admin/activity?limit=${limit}&offset=${offset}`,
    { signal: options?.signal },
  )
  return { events: data, total: meta?.total ?? data.length }
}

export async function getStorageUsage(signal?: AbortSignal) {
  const { data } = await requestJson<StorageUsage>('/api/v1/admin/storage', { signal })
  return data
}

export function overviewErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') return null
  if (error instanceof ApiError) {
    if (error.status === 404) return null
    if (error.status === 403) return 'Chỉ quản trị viên mới xem được mục này.'
    return error.message
  }
  if (error instanceof TypeError) return 'Không kết nối được backend.'
  return 'Không tải được dữ liệu. Thử lại.'
}

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  const rounded = value >= 100 ? Math.round(value) : Math.round(value * 10) / 10
  return `${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 }).format(rounded)} ${units[unit]}`
}
