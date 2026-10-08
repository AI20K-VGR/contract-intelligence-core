import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'
import { listDossiers, listDossiersErrorMessage } from '../api/dossiers'
import {
  formatBytes,
  getStorageUsage,
  listActivity,
  overviewErrorMessage,
  type ActivityEvent,
  type StorageUsage,
} from '../api/overview'
import {
  listUsers,
  userAdminErrorMessage,
  type ManagedUser,
  type ManagedUserRole,
  type ManagedUserStatus,
} from '../api/users'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

const PAGE_SIZE = 5

/** Thẻ trắng viền mảnh, chữ nhỏ, nhấn bằng màu chủ đạo tông nhạt. */
const CARD =
  'bg-white rounded-[12px] border border-tone-200 shadow-[0_2px_12px_rgba(0,0,0,0.04)]'
const INK = 'text-tone-900'
const MUTED = 'text-tone-500'
const ACCENT_FILL = 'bg-brand-100 text-brand-600'
const AVATAR_FILL = 'bg-brand-50 text-brand-700'

/** Màu icon từng ô thống kê theo bảng màu: petrol, navy, teal, blush. */
const STAT_TONE = {
  blue: ACCENT_FILL,
  indigo: 'bg-tone-100 text-brand-900',
  sky: 'bg-ice/50 text-brand-500',
  amber: 'bg-blush-100 text-blush-700',
} as const
type StatTone = keyof typeof STAT_TONE

const roleTone: Record<ManagedUserRole, string> = {
  ADMINISTRATOR: 'bg-brand-100 text-brand-700 ring-1 ring-brand-200',
  OPERATOR: 'bg-tone-100 text-brand-900 ring-1 ring-tone-200',
  REVIEWER: 'bg-blush-50 text-blush-700 ring-1 ring-blush-100',
}

const roleLabel: Record<ManagedUserRole, string> = {
  OPERATOR: 'Vận hành',
  REVIEWER: 'Thẩm định',
  ADMINISTRATOR: 'Quản trị',
}

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

function initials(name: string, email: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  }
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return email.slice(0, 2).toUpperCase()
}

function formatCount(value: number | null) {
  if (value === null) return '—'
  return new Intl.NumberFormat('vi-VN').format(value)
}

export function OverviewPage() {
  const { user } = useAuth()
  const isAdmin = user?.backendRole === 'ADMINISTRATOR'
  usePageTitle('Tổng quan hệ thống')
  const titleInHeader = useHeaderShowsPageTitle()
  const [queryInput, setQueryInput] = useState('')
  const [query, setQuery] = useState('')
  const [role, setRole] = useState<'all' | ManagedUserRole>('all')
  const [offset, setOffset] = useState(0)
  const [members, setMembers] = useState<ManagedUser[]>([])
  const [memberTotal, setMemberTotal] = useState(0)
  const [membersLoading, setMembersLoading] = useState(true)
  const [membersError, setMembersError] = useState<string | null>(null)
  const [userTotal, setUserTotal] = useState<number | null>(null)
  const [inviteTotal, setInviteTotal] = useState<number | null>(null)
  const [dossierTotal, setDossierTotal] = useState<number | null>(null)
  const [statsError, setStatsError] = useState<string | null>(null)
  const [storage, setStorage] = useState<StorageUsage | null>(null)
  const [storageLoading, setStorageLoading] = useState(true)
  const [storageMissing, setStorageMissing] = useState(false)
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [activityLoading, setActivityLoading] = useState(true)
  const [activityMissing, setActivityMissing] = useState(false)
  const [activityError, setActivityError] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(queryInput.trim())
      setOffset(0)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [queryInput])

  useEffect(() => {
    if (!isAdmin) {
      setMembers([])
      setMemberTotal(0)
      setMembersLoading(false)
      setMembersError(null)
      return
    }
    const controller = new AbortController()
    setMembersLoading(true)
    setMembersError(null)

    listUsers({
      q: query || undefined,
      role: role === 'all' ? undefined : role,
      limit: PAGE_SIZE,
      offset,
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return
        setMembers(result.users)
        setMemberTotal(result.total)
      })
      .catch((err: unknown) => {
        const message = userAdminErrorMessage(err)
        if (!message || controller.signal.aborted) return
        setMembers([])
        setMemberTotal(0)
        setMembersError(message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setMembersLoading(false)
      })

    return () => controller.abort()
  }, [query, role, offset, isAdmin])

  useEffect(() => {
    const controller = new AbortController()
    setStatsError(null)

    const users = isAdmin
      ? listUsers({ limit: 1, offset: 0, signal: controller.signal })
      : Promise.resolve({ users: [], total: 0 })
    const invites = isAdmin
      ? listUsers({
          status: 'invited' as const,
          limit: 1,
          offset: 0,
          signal: controller.signal,
        })
      : Promise.resolve({ users: [], total: 0 })
    const dossiers = listDossiers({ limit: 1, offset: 0, signal: controller.signal })

    Promise.allSettled([users, invites, dossiers]).then((results) => {
      if (controller.signal.aborted) return
      const [usersResult, invitesResult, dossiersResult] = results
      const messages: string[] = []

      if (usersResult.status === 'fulfilled') {
        setUserTotal(usersResult.value.total)
      } else {
        setUserTotal(null)
        const message = userAdminErrorMessage(usersResult.reason)
        if (message) messages.push(message)
      }

      if (invitesResult.status === 'fulfilled') {
        setInviteTotal(invitesResult.value.total)
      } else {
        setInviteTotal(null)
        const message = userAdminErrorMessage(invitesResult.reason)
        if (message && !messages.includes(message)) messages.push(message)
      }

      if (dossiersResult.status === 'fulfilled') {
        setDossierTotal(dossiersResult.value.total)
      } else {
        setDossierTotal(null)
        const message = listDossiersErrorMessage(dossiersResult.reason)
        if (message) messages.push(message)
      }

      setStatsError(messages.length > 0 ? messages.join(' ') : null)
    })

    return () => controller.abort()
  }, [isAdmin])

  useEffect(() => {
    const controller = new AbortController()
    setActivityLoading(true)
    setActivityError(null)
    setActivityMissing(false)
    setStorageLoading(true)
    setStorageMissing(false)

    listActivity({ signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return
        setActivity(result.events)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        if (err instanceof ApiError && err.status === 404) {
          setActivity([])
          setActivityMissing(true)
          return
        }
        const message = overviewErrorMessage(err)
        if (!message) return
        setActivity([])
        setActivityError(message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setActivityLoading(false)
      })

    getStorageUsage(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setStorage(result)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setStorage(null)
        setStorageMissing(!(err instanceof ApiError) || err.status === 404)
      })
      .finally(() => {
        if (!controller.signal.aborted) setStorageLoading(false)
      })

    return () => controller.abort()
  }, [])

  const from = members.length === 0 ? 0 : offset + 1
  const to = offset + members.length
  const hasPrev = offset > 0
  const hasNext = offset + PAGE_SIZE < memberTotal

  return (
    <div className="flex flex-col w-full gap-space-lg">
      {titleInHeader ? null : (
        <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
          Tổng quan hệ thống
        </h1>
      )}

      {statsError ? (
        <div className="px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm">
          {statsError}
        </div>
      ) : null}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-md">
        {isAdmin ? (
          <StatCard
            icon="group"
            label="Tổng người dùng"
            to="/nguoi-dung-phan-quyen"
            value={formatCount(userTotal)}
          />
        ) : null}
        <StatCard
          icon="inventory_2"
          tone="indigo"
          label="Hồ sơ hoạt động"
          to="/ho-so"
          value={formatCount(dossierTotal)}
        />
        <StorageCard
          storage={storage}
          loading={storageLoading}
          missing={storageMissing}
        />
        {isAdmin ? (
          <StatCard
            icon="mark_email_unread"
            tone="amber"
            label="Lời mời chờ duyệt"
            to="/nguoi-dung-phan-quyen"
            value={formatCount(inviteTotal)}
          />
        ) : null}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
        {isAdmin ? (
        <div
          className={`lg:col-span-8 flex flex-col overflow-hidden ${CARD}`}
        >
          <div className="p-space-lg flex flex-col sm:flex-row sm:items-center justify-between gap-space-md">
            <div>
              <h2 className={`text-[16px] font-medium ${INK}`}>
                Thành viên nhóm
              </h2>
            </div>
            <div className="flex items-center gap-space-sm flex-wrap">
              <div className="relative flex items-center">
                <MaterialIcon
                  name="search"
                  className="absolute left-2.5 text-secondary text-[16px]"
                />
                <input
                  className="pl-8 pr-space-md py-2 bg-tone-100 text-tone-900 rounded-[8px] font-body-sm text-body-sm placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-1 focus:ring-brand-300 w-44 sm:w-56"
                  placeholder="Tìm theo tên, email..."
                  type="search"
                  value={queryInput}
                  onChange={(event) => setQueryInput(event.target.value)}
                />
              </div>
              <div className="relative">
                <select
                  className="appearance-none bg-tone-100 text-tone-900 font-body-sm text-body-sm py-2 pl-4 pr-8 rounded-[8px] focus:outline-none focus:ring-1 focus:ring-brand-300 cursor-pointer"
                  value={role}
                  aria-label="Vai trò"
                  onChange={(event) => {
                    setRole(event.target.value as 'all' | ManagedUserRole)
                    setOffset(0)
                  }}
                >
                  <option value="all">Tất cả vai trò</option>
                  <option value="ADMINISTRATOR">Quản trị</option>
                  <option value="OPERATOR">Vận hành</option>
                  <option value="REVIEWER">Thẩm định</option>
                </select>
                <MaterialIcon
                  name="expand_more"
                  className="absolute right-2.5 top-2.5 pointer-events-none text-secondary text-[16px]"
                />
              </div>
            </div>
          </div>

          {membersError ? (
            <div className="mx-space-lg mb-space-md px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm">
              {membersError}
            </div>
          ) : null}

          <div className="w-full">
            <table className="w-full text-left text-on-surface font-body-sm text-body-sm table-fixed">
              <thead>
                <tr className={`${MUTED} text-[11px] font-semibold uppercase tracking-[0.06em] border-y border-tone-100`}>
                  <th className="py-3 px-space-lg w-[40%]" scope="col">
                    Thành viên
                  </th>
                  <th className="py-3 px-space-md w-[18%]" scope="col">
                    Vai trò
                  </th>
                  <th className="py-3 px-space-md w-[22%]" scope="col">
                    Đăng nhập gần nhất
                  </th>
                  <th className="py-3 px-space-md w-[20%]" scope="col">
                    Trạng thái
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-tone-100">
                {membersLoading && members.length === 0 ? (
                  <tr>
                    <td className="py-10 px-space-lg text-secondary" colSpan={4}>
                      Đang tải danh sách thành viên…
                    </td>
                  </tr>
                ) : null}
                {!membersLoading && members.length === 0 ? (
                  <tr>
                    <td className="py-12 px-space-lg" colSpan={4}>
                      <div className="flex flex-col items-center gap-space-sm text-center">
                        <MaterialIcon
                          name="group"
                          className="text-secondary text-[28px]"
                        />
                        <p className="font-title-sm text-title-sm text-on-surface">
                          {membersError
                            ? 'Chưa tải được danh sách'
                            : 'Chưa có thành viên khớp bộ lọc'}
                        </p>
                        <p className="font-body-sm text-body-sm text-secondary max-w-md">
                          {membersError
                            ? 'Danh sách hiện khi backend có API quản lý người dùng.'
                            : 'Mời thành viên để họ nhận email đặt mật khẩu.'}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : null}
                {members.map((member) => (
                  <MemberRow key={member.id} member={member} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="px-space-lg py-space-md border-t border-tone-100 flex items-center justify-between">
            <span className="font-body-sm text-body-sm text-secondary">
              Hiển thị{' '}
              <span className="font-semibold text-on-surface">
                {from} - {to}
              </span>{' '}
              của{' '}
              <span className="font-semibold text-on-surface">{memberTotal}</span>{' '}
              thành viên
            </span>
            <div className="flex items-center gap-space-xs">
              <button
                className="px-4 py-1.5 rounded-[8px] border border-tone-200 bg-white text-tone-900 hover:bg-tone-100 font-label-sm text-label-sm transition-colors disabled:text-tone-300 disabled:hover:bg-white disabled:cursor-not-allowed"
                disabled={!hasPrev || membersLoading}
                type="button"
                onClick={() =>
                  setOffset((current) => Math.max(0, current - PAGE_SIZE))
                }
              >
                Trước
              </button>
              <button
                className="px-4 py-1.5 rounded-[8px] bg-brand-100 text-brand-700 font-medium hover:bg-brand-200 font-label-sm text-label-sm transition-colors disabled:bg-brand-50 disabled:text-tone-300 disabled:font-normal disabled:cursor-not-allowed"
                disabled={!hasNext || membersLoading}
                type="button"
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
              >
                Sau
              </button>
            </div>
          </div>
        </div>
        ) : null}

        <div
          className={`${isAdmin ? 'lg:col-span-4' : 'lg:col-span-12'} flex flex-col p-space-lg min-h-0 overflow-hidden lg:h-[380px] ${CARD}`}
        >
          <div className="flex items-center justify-between mb-space-md shrink-0">
            <div className="flex items-center gap-space-xs min-w-0">
              <h2 className={`text-[16px] font-medium ${INK} truncate`}>
                Hoạt động gần đây
              </h2>
            </div>
            <Link
              className="font-label-sm text-label-sm font-semibold text-tone-900 underline-offset-4 hover:underline shrink-0"
              to="/nhat-ky-hoat-dong"
            >
              Xem tất cả
            </Link>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {activityLoading ? (
              <p className="font-body-sm text-body-sm text-secondary py-space-md">
                Đang tải hoạt động…
              </p>
            ) : null}
            {!activityLoading && activityError ? (
              <p className="font-body-sm text-body-sm text-error py-space-md">{activityError}</p>
            ) : null}
            {!activityLoading && !activityError && activity.length === 0 ? (
              <div className="flex flex-col items-start gap-space-sm py-space-md">
                <MaterialIcon name="history" className="text-secondary text-[28px]" />
                <p className="font-title-sm text-title-sm text-on-surface">
                  Chưa có nhật ký hoạt động
                </p>
                <p className="font-body-sm text-body-sm text-secondary">
                  {activityMissing
                    ? 'Backend chưa có API hoạt động toàn hệ thống. Nhật ký theo từng hồ sơ nằm ở màn rà soát.'
                    : 'Tạo hồ sơ, mời thành viên hoặc rà soát để sự kiện hiện ở đây.'}
                </p>
              </div>
            ) : null}
            {!activityLoading && activity.length > 0 ? (
              <ul className="flex flex-col gap-space-sm">
                {activity.map((event) => (
                  <li key={event.id} className="flex items-start gap-space-sm rounded-[10px] border border-tone-100 bg-tone-50 p-3">
                    <span
                      aria-hidden="true"
                      className={`w-8 h-8 rounded-full ${AVATAR_FILL} flex items-center justify-center text-[11px] font-bold shrink-0`}
                    >
                      {initials(event.actor_display_name ?? '', event.actor_display_name ?? '?')}
                    </span>
                    <span className="flex flex-col gap-0.5 min-w-0">
                      <span className={`font-body-sm text-body-sm font-semibold ${INK}`}>
                        {event.actor_display_name
                          ? `${event.actor_display_name} · ${event.title}`
                          : event.title}
                      </span>
                      <span className={`text-[12px] ${MUTED}`}>
                        {formatWhen(event.occurred_at)}
                      </span>
                      {event.detail ? (
                        <span className={`text-[12px] ${MUTED} truncate`}>
                          {event.detail}
                        </span>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

function StorageCard({
  storage,
  loading,
  missing,
}: {
  storage: StorageUsage | null
  loading: boolean
  missing: boolean
}) {
  const quota = storage?.quota_bytes ?? null
  const used = storage?.used_bytes ?? 0
  const percent =
    quota && quota > 0 ? Math.min(100, Math.round((used / quota) * 100)) : null
  let emptyNote = 'Không tải được dung lượng lưu trữ.'
  if (loading) emptyNote = 'Đang tải dung lượng…'
  else if (missing) emptyNote = 'Backend chưa có API dung lượng lưu trữ.'

  return (
    <div className={`${CARD} px-space-lg py-space-md flex flex-col`}>
      <CardHead icon="cloud_done" label="Dung lượng" tone="sky" />
      {storage ? (
        <div className="mt-space-sm">
          <span className={`text-[26px] leading-none font-semibold ${INK}`}>
            {formatBytes(used)}
          </span>
          {percent !== null ? (
            <div className="mt-space-sm">
              <div className="h-1.5 rounded-full bg-brand-100 overflow-hidden">
                <div className="h-full rounded-full bg-brand-600" style={{ width: `${percent}%` }} />
              </div>
              <p className={`text-[12px] ${MUTED} mt-space-xs`}>
                {percent}% của {formatBytes(quota ?? 0)}
              </p>
            </div>
          ) : (
            <p className={`text-[12px] ${MUTED} mt-space-xs`}>
              Tổng dung lượng tệp đã tải lên.
            </p>
          )}
        </div>
      ) : (
        <div className="mt-space-md">
          <span className={`text-[20px] font-bold ${MUTED}`}>Chưa có số liệu</span>
          <p className={`text-[12px] ${MUTED} mt-space-xs`}>{emptyNote}</p>
        </div>
      )}
    </div>
  )
}

/** Nhãn bên trái, icon trong ô vuông màu nhạt bên phải. */
function CardHead({
  icon,
  label,
  tone = 'blue',
}: {
  icon: string
  label: string
  tone?: StatTone
}) {
  return (
    <div className="flex items-center justify-between gap-space-sm">
      <span className="text-[13px] font-medium text-tone-700">{label}</span>
      <span className={`w-7 h-7 rounded-[6px] ${STAT_TONE[tone]} flex items-center justify-center shrink-0`}>
        <MaterialIcon name={icon} className="text-[16px]" />
      </span>
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
  to,
  tone,
}: {
  icon: string
  label: string
  value: string
  to?: string
  tone?: StatTone
}) {
  const body = (
    <>
      <CardHead icon={icon} label={label} tone={tone} />
      <div className="mt-space-sm">
        <span className={`text-[26px] leading-none font-semibold ${INK}`}>
          {value}
        </span>
      </div>
    </>
  )
  const className = `${CARD} px-space-lg py-space-md flex flex-col`
  if (!to) {
    return <div className={className}>{body}</div>
  }
  return (
    <Link
      className={`${className} transition-all hover:border-brand-200 hover:shadow-[0_6px_20px_rgba(0,0,0,0.07)]`}
      to={to}
    >
      {body}
    </Link>
  )
}

function MemberRow({ member }: { member: ManagedUser }) {
  const muted = member.status === 'disabled' || member.status === 'invited'
  return (
    <tr className="hover:bg-tone-50 transition-colors">
      <td className="py-3.5 px-space-lg">
        <div className="flex items-center gap-space-md">
          <div
            className={`w-9 h-9 rounded-full flex items-center justify-center text-[12px] font-medium shrink-0 ${
              roleTone[member.role]
            } ${muted ? 'opacity-60' : ''}`}
          >
            {initials(member.display_name, member.email)}
          </div>
          <div className="flex flex-col min-w-0">
            <span
              className={`font-body-sm text-body-sm font-semibold ${INK} truncate ${
                muted ? 'opacity-75' : ''
              }`}
            >
              {member.display_name}
            </span>
            <span className={`text-[12px] ${MUTED} truncate`}>{member.email}</span>
          </div>
        </div>
      </td>
      <td className="py-3.5 px-space-md">
        <span
          className={`inline-flex items-center px-2.5 py-1 rounded-[6px] text-[12px] font-medium whitespace-nowrap ${
            roleTone[member.role]
          }`}
        >
          {roleLabel[member.role]}
        </span>
      </td>
      <td className={`py-3.5 px-space-md ${MUTED} break-words`}>
        {member.status === 'invited'
          ? 'Chưa đăng nhập'
          : formatWhen(member.last_login_at)}
      </td>
      <td className="py-3.5 px-space-md">
        <StatusBadge status={member.status} />
      </td>
    </tr>
  )
}

function StatusBadge({ status }: { status: ManagedUserStatus }) {
  const pill =
    'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[6px] bg-tone-100 text-tone-700 whitespace-nowrap text-[12px] font-medium'
  if (status === 'active') {
    return (
      <span className={`${pill}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-[#22a55e]" />
        Đang hoạt động
      </span>
    )
  }
  if (status === 'invited') {
    return (
      <span className={`${pill}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-brand-300" />
        Đã mời
      </span>
    )
  }
  return (
    <span className={`${pill} text-[#b42318]`}>
      <span className="w-1.5 h-1.5 rounded-full bg-[#e5484d]" />
      Đã khóa
    </span>
  )
}
