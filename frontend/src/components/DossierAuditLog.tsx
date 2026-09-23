import { useMemo, useState } from 'react'
import { MaterialIcon } from './icons'
import {
  PAGE_SIZE,
  LEDGER_HASH,
  auditEvents,
  auditTypeCounts,
  auditUsers,
  type AuditEvent,
  type AuditType,
} from '../data/auditLog'

type FilterType = AuditType | 'all'

const typeFilters: Array<{
  id: FilterType
  label: string
  count: number
  dot?: string
}> = [
  { id: 'all', label: 'Tất cả', count: auditTypeCounts.all },
  {
    id: 'verified',
    label: 'Đã xác minh',
    count: auditTypeCounts.verified,
    dot: 'bg-emerald-600',
  },
  {
    id: 'edited',
    label: 'Đã chỉnh sửa',
    count: auditTypeCounts.edited,
    dot: 'bg-amber-500',
  },
  {
    id: 'flagged',
    label: 'Cảnh báo / Sai lệch',
    count: auditTypeCounts.flagged,
    dot: 'bg-error',
  },
  {
    id: 'viewed',
    label: 'Đã xem',
    count: auditTypeCounts.viewed,
    dot: 'bg-secondary',
  },
]

function actionBadge(type: AuditType) {
  if (type === 'edited') {
    return (
      <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-800 px-space-xs py-0.5 rounded font-label-sm text-label-sm font-semibold">
        <MaterialIcon name="edit_note" className="text-[14px]" />
        <span>Đã chỉnh sửa</span>
      </span>
    )
  }
  if (type === 'flagged') {
    return (
      <span className="inline-flex items-center gap-1 bg-error-container text-error px-space-xs py-0.5 rounded font-label-sm text-label-sm font-semibold">
        <MaterialIcon name="flag" className="text-[14px]" />
        <span>Cảnh báo sai lệch</span>
      </span>
    )
  }
  if (type === 'verified') {
    return (
      <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-800 px-space-xs py-0.5 rounded font-label-sm text-label-sm font-semibold">
        <MaterialIcon name="check_circle" className="text-[14px]" />
        <span>Đã xác minh</span>
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 bg-surface-container text-on-surface-variant px-space-xs py-0.5 rounded font-label-sm text-label-sm font-medium">
      <MaterialIcon name="visibility" className="text-[14px]" />
      <span>Đã xem trích dẫn</span>
    </span>
  )
}

function ActorCell({ event }: { event: AuditEvent }) {
  return (
    <div className="flex items-center gap-space-sm">
      {event.actor.kind === 'ai' ? (
        <div className="w-7 h-7 rounded-[9999px] bg-error text-on-error flex items-center justify-center font-label-sm text-label-sm font-semibold shadow-sm">
          <MaterialIcon name="smart_toy" className="text-[14px]" />
        </div>
      ) : (
        <div
          className={`w-7 h-7 rounded-[9999px] flex items-center justify-center font-label-sm text-label-sm font-semibold shadow-sm ${
            event.actor.initials === 'HL'
              ? 'bg-secondary-container text-on-secondary-container'
              : event.actor.initials === 'TL'
                ? 'bg-secondary text-on-secondary'
                : 'bg-primary-container text-on-primary'
          }`}
        >
          {event.actor.initials}
        </div>
      )}
      <div className="flex flex-col">
        <span className="font-title-sm text-title-sm text-on-surface font-semibold leading-tight">
          {event.actor.name}
        </span>
        <span className="font-label-sm text-label-sm text-secondary leading-tight">
          {event.actor.role}
        </span>
      </div>
    </div>
  )
}

function DetailCell({ event }: { event: AuditEvent }) {
  if (event.type === 'edited' && event.diff) {
    return (
      <div className="flex flex-col gap-space-xs">
        <div className="font-body-sm text-body-sm font-semibold text-on-surface flex items-center justify-between gap-space-sm">
          <span>{event.title}</span>
          <span className="font-label-sm text-label-sm text-secondary bg-surface-container px-1.5 py-0.5 rounded shrink-0">
            Diff inline
          </span>
        </div>
        <div className="p-space-sm bg-surface-container-low rounded flex flex-col gap-space-xs font-body-sm text-body-sm">
          <div className="flex items-center flex-wrap gap-1 font-body-sm">
            <span className="text-secondary">{event.diff.label}</span>
            <span className="line-through text-error bg-error-container/50 px-1.5 py-0.5 rounded font-code-sm text-code-sm">
              {event.diff.from}
            </span>
            <span className="text-secondary font-bold">→</span>
            <span className="text-emerald-800 bg-emerald-100 px-1.5 py-0.5 rounded font-bold font-code-sm text-code-sm">
              {event.diff.to}
            </span>
          </div>
          {event.diff.note ? (
            <div className="italic text-on-surface-variant text-body-sm flex items-start gap-1">
              <MaterialIcon
                name="chat"
                className="text-[14px] text-secondary mt-0.5"
              />
              <span>{event.diff.note}</span>
            </div>
          ) : null}
        </div>
      </div>
    )
  }

  if (event.type === 'flagged') {
    return (
      <div className="flex flex-col gap-space-xs">
        <div className="text-error font-semibold flex items-center gap-1">
          <MaterialIcon
            name={event.icon ?? 'warning'}
            className="text-[16px]"
          />
          <span>{event.title}</span>
        </div>
        {event.detail ? (
          <p className="text-on-surface-variant font-body-sm text-body-sm leading-relaxed">
            {event.detail}
          </p>
        ) : null}
        {event.recommendation || event.extra ? (
          <div className="flex items-center gap-space-sm pt-1 flex-wrap">
            {event.recommendation ? (
              <span className="font-label-sm text-label-sm bg-surface-container px-2 py-0.5 rounded text-secondary font-medium">
                {event.recommendation}
              </span>
            ) : null}
            {event.extra ? (
              <button
                className="font-label-sm text-label-sm text-on-tertiary-fixed-variant hover:underline font-semibold flex items-center gap-0.5"
                type="button"
              >
                <span>{event.extra}</span>
                <MaterialIcon name="open_in_new" className="text-[12px]" />
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    )
  }

  if (event.type === 'verified' && event.extra?.includes('VIAC')) {
    return (
      <div className="flex flex-col gap-space-xs">
        <div className="font-body-sm text-body-sm text-on-surface font-medium">
          {event.title}
        </div>
        <div className="flex items-center gap-space-sm text-secondary font-label-sm text-label-sm flex-wrap">
          <span className="flex items-center gap-1 text-emerald-700 font-medium">
            <MaterialIcon name="verified" className="text-[14px]" />
            VIAC (Trung tâm Trọng tài Quốc tế Việt Nam)
          </span>
          <span>•</span>
          <span>Chứng thư số USB Token: VNPT-CA Validated</span>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="font-body-sm text-body-sm text-on-surface">
        {event.title}
      </div>
      {event.extra ? (
        <span className="font-label-sm text-label-sm text-secondary">
          {event.extra}
        </span>
      ) : null}
    </div>
  )
}

function matchesQuery(event: AuditEvent, term: string) {
  if (!term) return true
  const haystack = [
    event.time,
    event.date,
    event.actor.name,
    event.actor.role,
    event.location,
    event.title,
    event.detail,
    event.diff?.from,
    event.diff?.to,
    event.diff?.note,
    event.recommendation,
    event.extra,
    event.hash,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return haystack.includes(term)
}

export function DossierAuditLog() {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<FilterType>('all')
  const [userId, setUserId] = useState('all')
  const [page, setPage] = useState(1)
  const [showUsers, setShowUsers] = useState(false)
  const [showDates, setShowDates] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const term = query.toLowerCase().trim()
    return auditEvents.filter((event) => {
      if (filter !== 'all' && event.type !== filter) return false
      if (userId !== 'all' && event.actor.name !== userId) return false
      return matchesQuery(event, term)
    })
  }, [filter, query, userId])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const start = (currentPage - 1) * PAGE_SIZE
  const pageRows = filtered.slice(start, start + PAGE_SIZE)
  const userLabel =
    auditUsers.find((item) => item.id === userId)?.label ?? auditUsers[0].label

  function changeFilter(next: FilterType) {
    setFilter(next)
    setPage(1)
  }

  function copyHash(hash: string) {
    void navigator.clipboard.writeText(hash)
    setCopied(hash)
    window.setTimeout(() => setCopied(null), 1200)
  }

  return (
    <>
      <div className="bg-surface-container-lowest p-space-md rounded-xl shadow-sm flex flex-col gap-space-md">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-md items-center">
          <div className="lg:col-span-5 relative">
            <MaterialIcon
              name="search"
              className="absolute left-space-md top-1/2 -translate-y-1/2 text-secondary text-[18px]"
            />
            <input
              className="w-full h-10 pl-10 pr-space-md rounded bg-surface-container-low text-on-surface placeholder:text-secondary font-body-sm text-body-sm focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary-container transition-all"
              placeholder="Tìm theo nội dung thay đổi, điều khoản, người thực hiện..."
              type="text"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setPage(1)
              }}
            />
          </div>
          <div className="lg:col-span-4 relative">
            <button
              className="w-full flex items-center gap-space-xs bg-surface-container-low h-10 px-space-md rounded text-on-surface hover:bg-surface-container transition-colors"
              type="button"
              onClick={() => {
                setShowDates((current) => !current)
                setShowUsers(false)
              }}
            >
              <MaterialIcon
                name="calendar_today"
                className="text-secondary text-[18px]"
              />
              <span className="font-body-sm text-body-sm font-medium">
                20/10/2024 - 24/10/2024
              </span>
              <span className="font-label-sm text-label-sm text-secondary ml-auto">
                (Toàn bộ thời gian)
              </span>
              <MaterialIcon
                name="arrow_drop_down"
                className="text-secondary text-[16px]"
              />
            </button>
            {showDates ? (
              <div className="absolute z-20 mt-1 w-full bg-surface-container-lowest rounded shadow-md border border-outline-variant/40 p-space-sm font-label-sm text-label-sm text-secondary">
                Khoảng thời gian mock: 20–24/10/2024 (toàn bộ sự kiện).
              </div>
            ) : null}
          </div>
          <div className="lg:col-span-3 relative">
            <button
              className="w-full flex items-center gap-space-xs bg-surface-container-low h-10 px-space-md rounded text-on-surface hover:bg-surface-container transition-colors"
              type="button"
              onClick={() => {
                setShowUsers((current) => !current)
                setShowDates(false)
              }}
            >
              <MaterialIcon
                name="group"
                className="text-secondary text-[18px]"
              />
              <span className="font-body-sm text-body-sm font-medium truncate">
                {userLabel}
              </span>
              <MaterialIcon
                name="arrow_drop_down"
                className="text-secondary text-[16px] ml-auto"
              />
            </button>
            {showUsers ? (
              <div className="absolute z-20 mt-1 w-full bg-surface-container-lowest rounded shadow-md border border-outline-variant/40 overflow-hidden">
                {auditUsers.map((item) => (
                  <button
                    key={item.id}
                    className="w-full text-left px-space-md py-2 font-body-sm text-body-sm hover:bg-surface-container-low"
                    type="button"
                    onClick={() => {
                      setUserId(item.id)
                      setPage(1)
                      setShowUsers(false)
                    }}
                  >
                    {item.label}
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
          {typeFilters.map((item) => {
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
                onClick={() => changeFilter(item.id)}
              >
                {item.dot ? (
                  <span className={`w-2 h-2 rounded-[9999px] ${item.dot}`} />
                ) : null}
                <span>{item.label}</span>
                <span
                  className={`font-code-sm text-code-sm ${active ? 'opacity-80' : 'text-secondary'}`}
                >
                  ({item.count})
                </span>
              </button>
            )
          })}
          <div className="ml-auto hidden xl:flex items-center gap-space-xs text-secondary font-label-sm text-label-sm">
            <MaterialIcon name="lock" className="text-[14px]" />
            <span>Chống giả mạo sổ cái theo tiêu chuẩn ISO/IEC 27001</span>
          </div>
        </div>
      </div>

      <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col">
        <div className="overflow-x-auto w-full">
          <table className="w-full text-left font-body-sm text-body-sm">
            <thead className="bg-surface-container font-label-sm text-label-sm uppercase text-secondary">
              <tr>
                <th
                  className="py-space-md px-space-md whitespace-nowrap"
                  scope="col"
                >
                  <div className="flex items-center gap-1">
                    <span>Thời gian (UTC+7)</span>
                    <MaterialIcon
                      name="arrow_downward"
                      className="text-[16px] text-on-surface"
                    />
                  </div>
                </th>
                <th
                  className="py-space-md px-space-md whitespace-nowrap"
                  scope="col"
                >
                  Người thực hiện
                </th>
                <th
                  className="py-space-md px-space-md whitespace-nowrap"
                  scope="col"
                >
                  Hành động
                </th>
                <th
                  className="py-space-md px-space-md whitespace-nowrap"
                  scope="col"
                >
                  Vị trí tài liệu
                </th>
                <th
                  className="py-space-md px-space-md min-w-[380px]"
                  scope="col"
                >
                  Chi tiết & Đối soát Thay đổi
                </th>
                <th
                  className="py-space-md px-space-md text-right whitespace-nowrap"
                  scope="col"
                >
                  Mã băm khối
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container text-on-surface">
              {pageRows.length === 0 ? (
                <tr>
                  <td
                    className="py-space-lg px-space-md text-secondary font-body-sm text-body-sm"
                    colSpan={6}
                  >
                    Không có sự kiện khớp bộ lọc.
                  </td>
                </tr>
              ) : (
                pageRows.map((event) => (
                  <tr
                    key={event.id}
                    className={`hover:bg-surface-container-low transition-colors ${
                      event.type === 'flagged' ? 'bg-error-container/10' : ''
                    }`}
                  >
                    <td className="py-space-md px-space-md align-top whitespace-nowrap font-code-sm text-code-sm">
                      <div className="font-bold text-on-surface">
                        {event.time}
                      </div>
                      <div className="text-secondary">{event.date}</div>
                    </td>
                    <td className="py-space-md px-space-md align-top whitespace-nowrap">
                      <ActorCell event={event} />
                    </td>
                    <td className="py-space-md px-space-md align-top whitespace-nowrap">
                      {actionBadge(event.type)}
                    </td>
                    <td className="py-space-md px-space-md align-top whitespace-nowrap">
                      <span className="bg-surface-container px-space-xs py-0.5 rounded font-code-sm text-code-sm text-on-surface font-medium">
                        {event.location}
                      </span>
                    </td>
                    <td className="py-space-md px-space-md align-top">
                      <DetailCell event={event} />
                    </td>
                    <td className="py-space-md px-space-md align-top text-right whitespace-nowrap font-code-sm text-code-sm text-secondary">
                      <button
                        className="hover:text-primary-container"
                        type="button"
                        onClick={() => copyHash(event.hash)}
                      >
                        {copied === event.hash ? 'Đã chép' : event.hash}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="bg-surface-container-low p-space-md flex flex-col md:flex-row items-center justify-between gap-space-md font-body-sm text-body-sm">
          <div className="flex items-center gap-space-sm text-secondary font-code-sm text-code-sm">
            <MaterialIcon
              name="lock_clock"
              className="text-[18px] text-emerald-700"
            />
            <div className="flex flex-col sm:flex-row sm:items-center sm:gap-2">
              <span className="text-on-surface font-semibold">
                Mã hóa băm chuỗi SHA-256:
              </span>
              <span className="bg-surface-container px-space-xs py-0.5 rounded text-on-tertiary-fixed-variant select-all">
                {LEDGER_HASH}
              </span>
              <span className="text-emerald-700 font-semibold">
                • Sổ cái chống sửa đổi SOC 2 Type II
              </span>
            </div>
          </div>
          <div className="flex items-center gap-space-md ml-auto">
            <span className="text-secondary font-label-sm text-label-sm">
              Hiển thị{' '}
              <strong className="text-on-surface">
                {filtered.length === 0 ? 0 : start + 1} -{' '}
                {Math.min(start + PAGE_SIZE, filtered.length)}
              </strong>{' '}
              trên{' '}
              <strong className="text-on-surface">{filtered.length}</strong> sự
              kiện
            </span>
            <div className="flex items-center gap-1">
              <button
                className="w-8 h-8 rounded bg-surface-container-lowest hover:bg-surface-container text-on-surface-variant flex items-center justify-center transition-colors shadow-sm disabled:opacity-40"
                disabled={currentPage === 1}
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                <MaterialIcon name="chevron_left" className="text-[16px]" />
              </button>
              {Array.from({ length: totalPages }, (_, index) => index + 1).map(
                (item) => (
                  <button
                    key={item}
                    className={`w-8 h-8 rounded font-code-sm text-code-sm font-semibold flex items-center justify-center transition-colors ${
                      item === currentPage
                        ? 'bg-primary-container text-on-primary shadow-sm'
                        : 'bg-surface-container-lowest hover:bg-surface-container text-on-surface'
                    }`}
                    type="button"
                    onClick={() => setPage(item)}
                  >
                    {item}
                  </button>
                ),
              )}
              <button
                className="w-8 h-8 rounded bg-surface-container-lowest hover:bg-surface-container text-on-surface flex items-center justify-center transition-colors shadow-sm disabled:opacity-40"
                disabled={currentPage === totalPages}
                type="button"
                onClick={() =>
                  setPage((current) => Math.min(totalPages, current + 1))
                }
              >
                <MaterialIcon name="chevron_right" className="text-[16px]" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
