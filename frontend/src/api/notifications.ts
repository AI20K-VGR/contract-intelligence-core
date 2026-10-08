import { requestJson } from './client'
import { progressPath, structurePath } from '../data/dossiers'

/** Loại thông báo cá nhân BE gửi về. Loại lạ vẫn hiển thị, chỉ không có link. */
export type NotificationType =
  | 'analysis_succeeded'
  | 'analysis_failed'
  | 'dossier_approved'
  | 'dossier_rejected'
  | 'dossier_needs_more_evidence'
  | 'dossier_shared'
  | 'review_requested'

export type AppNotification = {
  id: string
  type: NotificationType | string
  title: string
  detail: string | null
  dossier_id: string | null
  dossier_name: string | null
  actor_display_name: string | null
  created_at: string
  read_at: string | null
}

export async function listNotifications(options?: {
  limit?: number
  offset?: number
  signal?: AbortSignal
}) {
  const limit = options?.limit ?? 10
  const offset = options?.offset ?? 0
  const { data, meta } = await requestJson<AppNotification[]>(
    `/api/v1/notifications?limit=${limit}&offset=${offset}`,
    { signal: options?.signal },
  )
  return { notifications: data, total: meta?.total ?? data.length }
}

export async function getUnreadCount(signal?: AbortSignal) {
  const { data } = await requestJson<{ count: number }>(
    '/api/v1/notifications/unread-count',
    { signal },
  )
  return data.count
}

export async function markNotificationRead(id: string) {
  await requestJson<unknown>(
    `/api/v1/notifications/${encodeURIComponent(id)}/read`,
    { method: 'POST' },
  )
}

export async function markAllNotificationsRead() {
  await requestJson<unknown>('/api/v1/notifications/read-all', { method: 'POST' })
}

export function notificationIcon(type: string) {
  switch (type) {
    case 'analysis_succeeded':
      return 'task_alt'
    case 'analysis_failed':
      return 'error'
    case 'dossier_approved':
      return 'verified'
    case 'dossier_rejected':
    case 'dossier_needs_more_evidence':
      return 'rule'
    case 'dossier_shared':
      return 'share'
    case 'review_requested':
      return 'rate_review'
    default:
      return 'notifications'
  }
}

/** Trang mở khi bấm vào thông báo; null nếu thông báo không gắn hồ sơ. */
export function notificationLink(notification: AppNotification) {
  const dossierId = notification.dossier_id
  if (!dossierId) return null
  switch (notification.type) {
    case 'analysis_succeeded':
    case 'analysis_failed':
      return progressPath(dossierId)
    default:
      return structurePath(dossierId)
  }
}
