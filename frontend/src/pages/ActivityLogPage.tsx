import { useEffect, useState } from 'react'
import {
  listActivity,
  overviewErrorMessage,
  type ActivityEvent,
} from '../api/overview'
import { MaterialIcon } from '../components/icons'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

const PAGE_SIZE = 20

const dateTime = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function formatWhen(value: string | null | undefined) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return dateTime.format(date)
}

function initials(email: string) {
  const local = email.split('@')[0] ?? email
  const parts = local.split(/[.\s_+-]+/).filter(Boolean)
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  }
  return local.slice(0, 2).toUpperCase() || '—'
}

export function ActivityLogPage() {
  usePageTitle('Nhật ký hoạt động')
  const titleInHeader = useHeaderShowsPageTitle()
  const [offset, setOffset] = useState(0)
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    listActivity({ limit: PAGE_SIZE, offset, signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return
        setEvents(result.events)
        setTotal(result.total)
        setError(null)
      })
      .catch((cause: unknown) => {
        const message = overviewErrorMessage(cause)
        if (message && !controller.signal.aborted) {
          setEvents([])
          setTotal(0)
          setError(message)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [offset])

  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + events.length, total)
  const hasPrev = offset > 0
  const hasNext = offset + PAGE_SIZE < total

  return (
    <div className="flex flex-col gap-space-md">
      {titleInHeader ? null : (
        <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
          Nhật ký hoạt động
        </h1>
      )}
      <p className="font-body-sm text-body-sm text-secondary">
        Mọi lần thêm, tạo, sửa và xóa trong tổ chức: ai làm, làm gì, lúc nào.
      </p>

      <div className="bg-surface-container-lowest rounded shadow-sm overflow-hidden">
        {error ? (
          <div className="mx-space-lg mt-space-md px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm">
            {error}
          </div>
        ) : null}

        <div className="w-full overflow-x-auto">
          <table className="w-full text-left text-on-surface font-body-sm text-body-sm min-w-[720px]">
            <thead>
              <tr className="bg-surface-container-low text-secondary font-label-sm text-label-sm uppercase tracking-wider">
                <th className="py-3 px-space-lg" scope="col">
                  Người thực hiện
                </th>
                <th className="py-3 px-space-md" scope="col">
                  Hành động
                </th>
                <th className="py-3 px-space-lg whitespace-nowrap" scope="col">
                  Thời gian
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-low">
              {loading && events.length === 0 ? (
                <tr>
                  <td className="py-10 px-space-lg text-secondary" colSpan={3}>
                    Đang tải nhật ký hoạt động…
                  </td>
                </tr>
              ) : null}
              {!loading && events.length === 0 ? (
                <tr>
                  <td className="py-12 px-space-lg" colSpan={3}>
                    <div className="flex flex-col items-center gap-space-sm text-center">
                      <MaterialIcon
                        name="history"
                        className="text-secondary text-[28px]"
                      />
                      <p className="font-title-sm text-title-sm text-on-surface">
                        Chưa có nhật ký hoạt động
                      </p>
                      <p className="font-body-sm text-body-sm text-secondary max-w-md">
                        Tạo hồ sơ, sửa, xóa hoặc đổi quyền để sự kiện hiện ở đây.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : null}
              {events.map((event) => {
                const actor = event.actor_display_name?.trim() || 'Hệ thống'
                return (
                  <tr
                    key={event.id}
                    className="hover:bg-surface-container-low/60 transition-colors"
                  >
                    <td className="py-3.5 px-space-lg">
                      <div className="flex items-center gap-space-md">
                        <div className="w-8 h-8 rounded-full bg-surface-container text-secondary flex items-center justify-center font-title-sm text-title-sm font-semibold shrink-0">
                          {initials(actor)}
                        </div>
                        <span className="font-title-sm text-title-sm text-on-surface">
                          {actor}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-space-md">
                      <div className="flex flex-col min-w-0">
                        <span className="font-title-sm text-title-sm text-on-surface">
                          {event.title}
                        </span>
                        {event.detail ? (
                          <span className="font-body-sm text-body-sm text-secondary truncate">
                            {event.detail}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="py-3.5 px-space-lg whitespace-nowrap text-secondary">
                      {formatWhen(event.occurred_at)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="p-space-md flex items-center justify-between">
          <span className="font-body-sm text-body-sm text-secondary">
            Hiển thị{' '}
            <span className="font-semibold text-on-surface">
              {from} - {to}
            </span>{' '}
            của <span className="font-semibold text-on-surface">{total}</span>{' '}
            hoạt động
          </span>
          <div className="flex items-center gap-space-xs">
            <button
              className="px-space-md py-1 rounded bg-surface-container-low text-on-surface hover:bg-surface-container font-label-sm text-label-sm transition-colors disabled:text-outline disabled:cursor-not-allowed"
              disabled={!hasPrev || loading}
              type="button"
              onClick={() =>
                setOffset((current) => Math.max(0, current - PAGE_SIZE))
              }
            >
              Trước
            </button>
            <button
              className="px-space-md py-1 rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm transition-colors disabled:text-outline disabled:cursor-not-allowed"
              disabled={!hasNext || loading}
              type="button"
              onClick={() => setOffset((current) => current + PAGE_SIZE)}
            >
              Sau
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
