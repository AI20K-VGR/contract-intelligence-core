import { useEffect, useMemo, useState } from 'react'
import {
  listActivity,
  overviewErrorMessage,
  type ActivityEvent,
} from '../api/overview'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { usePageTitle } from '../hooks/usePageTitle'

const FETCH_LIMIT = 50

type ActionType =
  | 'verified'
  | 'edited'
  | 'created'
  | 'uploaded'
  | 'added'
  | 'flagged'
  | 'viewed'
  | 'other'

const typeFilters: Array<{
  id: ActionType | 'all'
  label: string
  dot?: string
}> = [
  { id: 'all', label: 'Tất cả' },
  { id: 'created', label: 'Tạo mới', dot: 'bg-primary-container' },
  { id: 'uploaded', label: 'Tải lên', dot: 'bg-on-tertiary-fixed-variant' },
  { id: 'added', label: 'Thêm', dot: 'bg-secondary' },
  { id: 'edited', label: 'Đã chỉnh sửa', dot: 'bg-amber-500' },
  { id: 'verified', label: 'Đã xác minh', dot: 'bg-emerald-600' },
  { id: 'flagged', label: 'Cảnh báo / Từ chối', dot: 'bg-error' },
  { id: 'viewed', label: 'Đã xem', dot: 'bg-outline' },
  { id: 'other', label: 'Khác', dot: 'bg-outline-variant' },
]

function startsWithWord(text: string, word: string) {
  if (!text.startsWith(word)) return false
  const next = text.charAt(word.length)
  return next === '' || /[\s:.,]/.test(next)
}

function classifyTitle(title: string): ActionType {
  const text = title.trim().toLowerCase()
  if (
    ['xóa', 'xoá', 'từ chối', 'yêu cầu thêm', 'cảnh báo'].some((word) =>
      startsWithWord(text, word),
    ) ||
    text.includes('thất bại') ||
    text.includes('sai lệch')
  ) {
    return 'flagged'
  }
  if (['xem', 'truy cập', 'đã xem'].some((word) => startsWithWord(text, word))) {
    return 'viewed'
  }
  if (['xác nhận', 'phê duyệt', 'xác minh'].some((word) => startsWithWord(text, word))) {
    return 'verified'
  }
  if (['tải lên', 'upload'].some((word) => startsWithWord(text, word))) return 'uploaded'
  if (['thêm', 'mời'].some((word) => startsWithWord(text, word))) return 'added'
  if (startsWithWord(text, 'tạo')) return 'created'
  if (['sửa', 'chỉnh', 'cập nhật', 'đổi'].some((word) => startsWithWord(text, word))) {
    return 'edited'
  }
  return 'other'
}

function classify(event: { id: string; title: string }): ActionType {
  const id = event.id
  if (id.startsWith('document:')) return 'uploaded'
  if (id.startsWith('dossier:')) return 'created'
  if (id.startsWith('user:')) return 'added'
  if (id.startsWith('deleted:')) return 'flagged'
  if (id.startsWith('approval:') || id.startsWith('manifest:')) return 'verified'
  if (id.startsWith('run:')) return /thất bại/i.test(event.title) ? 'flagged' : 'other'
  if (id.startsWith('review:')) {
    const text = event.title.trim().toLowerCase()
    if (startsWithWord(text, 'xác nhận')) return 'verified'
    if (startsWithWord(text, 'từ chối') || startsWithWord(text, 'yêu cầu thêm')) {
      return 'flagged'
    }
    if (
      startsWithWord(text, 'sửa') ||
      startsWithWord(text, 'cập nhật') ||
      startsWithWord(text, 'chỉnh')
    ) {
      return 'edited'
    }
  }
  return classifyTitle(event.title)
}

const badgeStyle: Record<ActionType, { icon: string; label: string; className: string }> =
  {
    edited: {
      icon: 'edit_note',
      label: 'Đã chỉnh sửa',
      className: 'bg-amber-50 text-amber-800',
    },
    verified: {
      icon: 'check_circle',
      label: 'Đã xác minh',
      className: 'bg-emerald-50 text-emerald-800',
    },
    created: {
      icon: 'note_add',
      label: 'Tạo mới',
      className: 'bg-surface-container-high text-primary-container',
    },
    uploaded: {
      icon: 'upload_file',
      label: 'Tải lên',
      className: 'bg-surface-container text-on-tertiary-fixed-variant',
    },
    added: {
      icon: 'person_add',
      label: 'Thêm',
      className: 'bg-secondary-container text-on-secondary-container',
    },
    flagged: {
      icon: 'flag',
      label: 'Cảnh báo / Từ chối',
      className: 'bg-error-container text-error',
    },
    viewed: {
      icon: 'visibility',
      label: 'Đã xem',
      className: 'bg-surface-container text-on-surface-variant',
    },
    other: {
      icon: 'history',
      label: 'Khác',
      className: 'bg-surface-container text-on-surface-variant',
    },
  }

function actionBadge(type: ActionType) {
  const badge = badgeStyle[type]
  return (
    <span
      className={`inline-flex items-center gap-1 px-space-xs py-0.5 rounded font-label-sm text-label-sm font-semibold ${badge.className}`}
    >
      <MaterialIcon name={badge.icon} className="text-[14px]" />
      <span>{badge.label}</span>
    </span>
  )
}

function initials(name: string) {
  const local = name.split('@')[0] ?? name
  const parts = local.split(/[.\s_+-]+/).filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return local.slice(0, 2).toUpperCase() || '—'
}

function splitWhen(value: string | null | undefined) {
  if (!value) return { time: '—', day: '' }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return { time: '—', day: '' }
  return {
    time: date.toLocaleTimeString('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }),
    day: date.toLocaleDateString('vi-VN'),
  }
}

function shortId(id: string) {
  const compact = id.replace(/-/g, '')
  if (compact.length < 8) return `#${compact}`
  return `#${compact.slice(0, 4)}..${compact.slice(-4)}`
}

function avatarClass(type: ActionType) {
  if (type === 'flagged') return 'bg-error text-on-error'
  if (type === 'verified') return 'bg-emerald-700 text-white'
  if (type === 'uploaded' || type === 'added') return 'bg-secondary text-on-secondary'
  if (type === 'created') return 'bg-primary-container text-on-primary'
  if (type === 'viewed' || type === 'other') return 'bg-surface-container text-secondary'
  return 'bg-primary-container text-on-primary'
}

export function ActivityLogPage() {
  const { user } = useAuth()
  const seesEveryone = user?.backendRole === 'ADMINISTRATOR'
  usePageTitle('Nhật ký hoạt động')
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<ActionType | 'all'>('all')
  const [userId, setUserId] = useState('all')
  const [showUsers, setShowUsers] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    listActivity({ limit: FETCH_LIMIT, offset: 0, signal: controller.signal })
      .then(async (first) => {
        if (controller.signal.aborted) return
        const collected = [...first.events]
        let offset = first.events.length
        while (offset < first.total && !controller.signal.aborted) {
          const next = await listActivity({
            limit: FETCH_LIMIT,
            offset,
            signal: controller.signal,
          })
          collected.push(...next.events)
          if (next.events.length === 0) break
          offset += next.events.length
        }
        if (controller.signal.aborted) return
        const seen = new Set<string>()
        setEvents(
          collected.filter((event) => {
            if (seen.has(event.id)) return false
            seen.add(event.id)
            return true
          }),
        )
        setTotal(first.total)
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
  }, [])

  const users = useMemo(() => {
    const names = new Set<string>()
    for (const event of events) {
      const name = event.actor_display_name?.trim()
      if (name) names.add(name)
    }
    return ['all', ...names]
  }, [events])

  const classified = events.map((event) => ({
    event,
    type: classify(event),
  }))

  const counts: Record<ActionType | 'all', number> = {
    all: classified.length,
    verified: 0,
    edited: 0,
    created: 0,
    uploaded: 0,
    added: 0,
    flagged: 0,
    viewed: 0,
    other: 0,
  }
  for (const item of classified) counts[item.type] += 1

  const term = query.toLowerCase().trim()
  const filtered = classified.filter((item) => {
    if (filter !== 'all' && item.type !== filter) return false
    const actor = item.event.actor_display_name?.trim() || ''
    if (userId !== 'all' && actor !== userId) return false
    if (!term) return true
    return [actor, item.event.title, item.event.detail, item.event.id]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
      .includes(term)
  })

  const userLabel =
    userId === 'all' ? `Tất cả người dùng (${Math.max(users.length - 1, 0)})` : userId

  const rangeLabel = useMemo(() => {
    if (events.length === 0) return 'Toàn bộ thời gian'
    const times = events
      .map((event) => new Date(event.occurred_at).getTime())
      .filter((value) => !Number.isNaN(value))
    if (times.length === 0) return 'Toàn bộ thời gian'
    const format = (value: number) =>
      new Date(value).toLocaleDateString('vi-VN')
    return `${format(Math.min(...times))} - ${format(Math.max(...times))}`
  }, [events])

  return (
    <div className="flex h-[calc(100vh-6rem)] min-h-0 w-full flex-col gap-space-md">
      <div className="shrink-0 bg-surface-container-lowest p-space-md rounded-xl shadow-sm flex flex-col gap-space-md">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-md items-center">
          <div className="lg:col-span-5 relative">
            <MaterialIcon
              name="search"
              className="absolute left-space-md top-1/2 -translate-y-1/2 text-secondary text-[18px]"
            />
            <input
              className="w-full h-10 pl-10 pr-space-md rounded bg-surface-container-low text-on-surface placeholder:text-secondary font-body-sm text-body-sm focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary-container transition-all"
              placeholder="Tìm theo nội dung thay đổi, người thực hiện..."
              type="text"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
              }}
            />
          </div>
          <div className="lg:col-span-4 flex items-center gap-space-xs bg-surface-container-low h-10 px-space-md rounded text-on-surface">
            <MaterialIcon
              name="calendar_today"
              className="text-secondary text-[18px]"
            />
            <span className="font-body-sm text-body-sm font-medium">
              {rangeLabel}
            </span>
            <span className="font-label-sm text-label-sm text-secondary ml-auto">
              (Toàn bộ thời gian)
            </span>
          </div>
          <div className="lg:col-span-3 relative">
            {seesEveryone ? (
            <button
              className="w-full flex items-center gap-space-xs bg-surface-container-low h-10 px-space-md rounded text-on-surface hover:bg-surface-container transition-colors"
              type="button"
              onClick={() => setShowUsers((current) => !current)}
            >
              <MaterialIcon name="group" className="text-secondary text-[18px]" />
              <span className="font-body-sm text-body-sm font-medium truncate">
                {userLabel}
              </span>
              <MaterialIcon
                name="arrow_drop_down"
                className="text-secondary text-[16px] ml-auto"
              />
            </button>
            ) : (
              <div className="w-full flex items-center gap-space-xs bg-surface-container-low h-10 px-space-md rounded text-on-surface">
                <MaterialIcon name="person" className="text-secondary text-[18px]" />
                <span className="font-body-sm text-body-sm font-medium truncate">
                  {user?.email || user?.name || 'Bạn'}
                </span>
              </div>
            )}
            {seesEveryone && showUsers ? (
              <div className="absolute z-20 mt-1 w-full bg-surface-container-lowest rounded shadow-md border border-outline-variant/40 overflow-hidden max-h-64 overflow-y-auto">
                {users.map((name) => (
                  <button
                    key={name}
                    className="w-full text-left px-space-md py-2 font-body-sm text-body-sm hover:bg-surface-container-low"
                    type="button"
                    onClick={() => {
                      setUserId(name)
                      setShowUsers(false)
                    }}
                  >
                    {name === 'all'
                      ? `Tất cả người dùng (${Math.max(users.length - 1, 0)})`
                      : name}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-space-xs pt-space-xs">
          <span className="font-label-sm text-label-sm uppercase text-secondary font-semibold mr-space-xs">
            Phân loại:
          </span>
          {typeFilters
            .filter((item) => item.id === 'all' || counts[item.id] > 0)
            .map((item) => {
            const active = filter === item.id
            return (
              <button
                key={item.id}
                className={`flex items-center gap-1.5 px-space-md py-1 rounded font-label-md text-label-md transition-colors ${
                  active
                    ? 'bg-primary-container text-on-primary'
                    : 'bg-surface-container-low text-on-surface hover:bg-surface-container'
                }`}
                type="button"
                onClick={() => {
                  setFilter(item.id)
                }}
              >
                {item.dot ? (
                  <span className={`w-2 h-2 rounded-[9999px] ${item.dot}`} />
                ) : null}
                <span>{item.label}</span>
                <span
                  className={`font-code-sm text-code-sm ${active ? 'opacity-80' : 'text-secondary'}`}
                >
                  ({counts[item.id]})
                </span>
              </button>
            )
          })}
          <div className="ml-auto hidden xl:flex items-center gap-space-xs text-secondary font-label-sm text-label-sm">
            <MaterialIcon name="lock" className="text-[14px]" />
            <span>Nhật ký thao tác trong tổ chức</span>
          </div>
        </div>
      </div>

      <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col min-h-0 flex-1">
        {error ? (
          <div className="mx-space-md mt-space-md px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm">
            {error}
          </div>
        ) : null}
        <div className="min-h-0 flex-1 overflow-auto w-full">
          <table className="w-full text-left font-body-sm text-body-sm">
            <thead className="sticky top-0 z-10 bg-surface-container font-label-sm text-label-sm uppercase text-secondary">
              <tr>
                <th className="py-space-md px-space-md whitespace-nowrap" scope="col">
                  <div className="flex items-center gap-1">
                    <span>Thời gian (UTC+7)</span>
                    <MaterialIcon
                      name="arrow_downward"
                      className="text-[16px] text-on-surface"
                    />
                  </div>
                </th>
                <th className="py-space-md px-space-md whitespace-nowrap" scope="col">
                  Người thực hiện
                </th>
                <th className="py-space-md px-space-md whitespace-nowrap" scope="col">
                  Hành động
                </th>
                <th className="py-space-md px-space-md min-w-[280px]" scope="col">
                  Chi tiết
                </th>
                <th
                  className="py-space-md px-space-md text-right whitespace-nowrap"
                  scope="col"
                >
                  Mã sự kiện
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container text-on-surface">
              {loading && events.length === 0 ? (
                <tr>
                  <td
                    className="py-space-lg px-space-md text-secondary"
                    colSpan={5}
                  >
                    Đang tải nhật ký hoạt động…
                  </td>
                </tr>
              ) : null}
              {!loading && filtered.length === 0 ? (
                <tr>
                  <td className="py-12 px-space-md" colSpan={5}>
                    <div className="flex flex-col items-center gap-space-sm text-center">
                      <MaterialIcon
                        name="history"
                        className="text-secondary text-[28px]"
                      />
                      <p className="font-title-sm text-title-sm text-on-surface">
                        {events.length === 0
                          ? 'Chưa có nhật ký hoạt động'
                          : 'Không có sự kiện khớp bộ lọc.'}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : null}
              {filtered.map(({ event, type }) => {
                const actor = event.actor_display_name?.trim() || ''
                const when = splitWhen(event.occurred_at)
                return (
                  <tr
                    key={event.id}
                    className={`hover:bg-surface-container-low transition-colors ${
                      type === 'flagged' ? 'bg-error-container/10' : ''
                    }`}
                  >
                    <td className="py-space-md px-space-md align-top whitespace-nowrap font-code-sm text-code-sm">
                      <div className="font-bold text-on-surface">{when.time}</div>
                      <div className="text-secondary">{when.day}</div>
                    </td>
                    <td className="py-space-md px-space-md align-top whitespace-nowrap">
                      <div className="flex items-center gap-space-sm">
                        <div
                          className={`w-7 h-7 rounded-[9999px] flex items-center justify-center font-label-sm text-label-sm font-semibold shadow-sm ${avatarClass(type)}`}
                        >
                          {initials(actor)}
                        </div>
                        <span className="font-title-sm text-title-sm text-on-surface font-semibold leading-tight">
                          {actor}
                        </span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md align-top whitespace-nowrap">
                      {actionBadge(type)}
                    </td>
                    <td className="py-space-md px-space-md align-top">
                      <div className="font-body-sm text-body-sm font-semibold text-on-surface">
                        {event.title}
                      </div>
                      {event.detail ? (
                        <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-xs">
                          {event.detail}
                        </p>
                      ) : null}
                    </td>
                    <td className="py-space-md px-space-md align-top text-right whitespace-nowrap font-code-sm text-code-sm text-secondary">
                      {shortId(event.id)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="bg-surface-container-low p-space-md font-body-sm text-body-sm">
          <span className="text-secondary font-label-sm text-label-sm">
            {total > events.length
              ? `Đang hiện ${events.length} sự kiện gần nhất trên ${total}. `
              : null}
            <strong className="text-on-surface">{filtered.length}</strong> sự kiện
          </span>
        </div>
      </div>
    </div>
  )
}
