import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import {
  type AppNotification,
  getUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  notificationIcon,
  notificationLink,
} from '../api/notifications'
import { MaterialIcon } from './icons'

const POLL_MS = 30_000

type NotificationBellProps = {
  buttonClassName: string
  dotClassName: string
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date)
}

/** BE chưa có API thông báo thì coi như không có thông báo, không báo lỗi. */
function isMissingApi(error: unknown) {
  return error instanceof ApiError && (error.status === 404 || error.status === 405)
}

export function NotificationBell({ buttonClassName, dotClassName }: NotificationBellProps) {
  const navigate = useNavigate()
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)
  const [items, setItems] = useState<AppNotification[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshCount = useCallback(async (signal?: AbortSignal) => {
    try {
      setUnread(await getUnreadCount(signal))
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setUnread(0)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refreshCount(controller.signal)
    const timer = window.setInterval(() => void refreshCount(), POLL_MS)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [refreshCount])

  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    listNotifications({ limit: 10, signal: controller.signal })
      .then(({ notifications }) => setItems(notifications))
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setItems([])
        if (!isMissingApi(err)) setError('Không tải được thông báo. Thử lại sau.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [open])

  useEffect(() => {
    if (!open) return
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const openNotification = async (item: AppNotification) => {
    if (!item.read_at) {
      setItems((prev) =>
        prev.map((n) => (n.id === item.id ? { ...n, read_at: new Date().toISOString() } : n)),
      )
      setUnread((count) => Math.max(0, count - 1))
      markNotificationRead(item.id).catch(() => void refreshCount())
    }
    const link = notificationLink(item)
    if (link) {
      setOpen(false)
      navigate(link)
    }
  }

  const markAll = async () => {
    const now = new Date().toISOString()
    setItems((prev) => prev.map((n) => (n.read_at ? n : { ...n, read_at: now })))
    setUnread(0)
    try {
      await markAllNotificationsRead()
    } catch {
      void refreshCount()
    }
  }

  const badge = unread > 99 ? '99+' : String(unread)

  return (
    <div ref={rootRef} className="relative">
      <button
        aria-label={unread > 0 ? `Thông báo, ${unread} chưa đọc` : 'Thông báo'}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={buttonClassName}
        type="button"
        onClick={() => setOpen((value) => !value)}
      >
        <MaterialIcon name="notifications" className="text-[20px]" />
        {unread > 0 && <span className={dotClassName} aria-hidden="true" />}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Thông báo"
          className="absolute right-0 top-full mt-2 w-[360px] max-w-[calc(100vw-32px)] rounded-lg border border-outline-variant bg-surface shadow-lg z-50 overflow-hidden"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant">
            <span className="font-label-md text-label-md text-on-surface">
              Thông báo{unread > 0 ? ` (${badge})` : ''}
            </span>
            {unread > 0 && (
              <button
                type="button"
                className="font-label-sm text-label-sm text-primary hover:underline"
                onClick={() => void markAll()}
              >
                Đánh dấu tất cả đã đọc
              </button>
            )}
          </div>

          <div className="max-h-[420px] overflow-y-auto">
            {loading ? (
              <p className="px-4 py-6 text-center text-body-sm text-secondary">Đang tải...</p>
            ) : error ? (
              <p className="px-4 py-6 text-center text-body-sm text-error">{error}</p>
            ) : items.length === 0 ? (
              <p className="px-4 py-6 text-center text-body-sm text-secondary">Chưa có thông báo</p>
            ) : (
              <ul>
                {items.map((item) => {
                  const isUnread = !item.read_at
                  return (
                    <li key={item.id} className="border-b border-outline-variant last:border-b-0">
                      <button
                        type="button"
                        onClick={() => void openNotification(item)}
                        className={`w-full text-left flex gap-3 px-4 py-3 hover:bg-surface-container transition-colors ${
                          isUnread ? 'bg-surface-container-low' : ''
                        }`}
                      >
                        <MaterialIcon
                          name={notificationIcon(item.type)}
                          className={`text-[20px] shrink-0 mt-0.5 ${
                            item.type === 'analysis_failed' ? 'text-error' : 'text-secondary'
                          }`}
                        />
                        <span className="flex-1 min-w-0">
                          <span
                            className={`block text-body-sm text-on-surface ${
                              isUnread ? 'font-semibold' : ''
                            }`}
                          >
                            {item.title}
                          </span>
                          {(item.dossier_name || item.detail) && (
                            <span className="block text-label-sm text-secondary truncate">
                              {item.dossier_name ?? item.detail}
                            </span>
                          )}
                          <span className="block text-label-sm text-secondary mt-0.5">
                            {item.actor_display_name ? `${item.actor_display_name} · ` : ''}
                            {formatTime(item.created_at)}
                          </span>
                        </span>
                        {isUnread && (
                          <span className="w-2 h-2 rounded-full bg-error shrink-0 mt-2" aria-label="Chưa đọc" />
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
