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
import { MaterialIcon } from '../components/icons'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

const PAGE_SIZE = 5

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
  }, [query, role, offset])

  useEffect(() => {
    const controller = new AbortController()
    setStatsError(null)

    const users = listUsers({ limit: 1, offset: 0, signal: controller.signal })
    const invites = listUsers({
      status: 'invited',
      limit: 1,
      offset: 0,
      signal: controller.signal,
    })
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
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setActivityLoading(true)
    setActivityError(null)
    setActivityMissing(false)
    setStorageLoading(true)
    setStorageMissing(false)

    listActivity(controller.signal)
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
        <StatCard
          icon="group"
          label="Tổng người dùng"
          to="/nguoi-dung-phan-quyen"
          value={formatCount(userTotal)}
        />
        <StatCard
          icon="inventory_2"
          label="Hồ sơ hoạt động"
          to="/ho-so"
          value={formatCount(dossierTotal)}
        />
        <StorageCard
          storage={storage}
          loading={storageLoading}
          missing={storageMissing}
        />
        <StatCard
          icon="mark_email_unread"
          label="Lời mời chờ duyệt"
          to="/nguoi-dung-phan-quyen"
          value={formatCount(inviteTotal)}
        />
      </div>

      <div className="w-full bg-surface-container-low px-space-lg py-space-md rounded flex items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-md min-w-0">
          <div className="w-7 h-7 rounded bg-surface-container flex items-center justify-center shrink-0">
            <MaterialIcon name="lock" className="text-secondary text-[16px]" />
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant truncate md:whitespace-normal">
            <strong className="font-title-sm text-title-sm text-on-surface">
              Chính sách:
            </strong>{' '}
            Admin chỉ xem được hồ sơ khi người dùng chủ động chia sẻ.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
        <div className="lg:col-span-8 flex flex-col bg-surface-container-lowest rounded shadow-sm overflow-hidden">
          <div className="p-space-lg flex flex-col sm:flex-row sm:items-center justify-between gap-space-md bg-surface-container-lowest">
            <div>
              <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">
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
                  className="pl-8 pr-space-md py-1.5 bg-surface-container text-on-surface rounded font-body-sm text-body-sm placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-1 focus:ring-secondary w-44 sm:w-56"
                  placeholder="Tìm theo tên, email..."
                  type="search"
                  value={queryInput}
                  onChange={(event) => setQueryInput(event.target.value)}
                />
              </div>
              <div className="relative">
                <select
                  className="appearance-none bg-surface-container text-on-surface font-body-sm text-body-sm py-1.5 pl-3 pr-8 rounded focus:outline-none cursor-pointer"
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
                  className="absolute right-2 top-2 pointer-events-none text-secondary text-[16px]"
                />
              </div>
            </div>
          </div>

          {membersError ? (
            <div className="mx-space-lg mb-space-md px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm">
              {membersError}
            </div>
          ) : null}

          <div className="w-full overflow-x-auto">
            <table className="w-full text-left text-on-surface font-body-sm text-body-sm min-w-[720px]">
              <thead>
                <tr className="bg-surface-container-low text-secondary font-label-sm text-label-sm uppercase tracking-wider">
                  <th className="py-3 px-space-lg" scope="col">
                    Thành viên
                  </th>
                  <th className="py-3 px-space-md" scope="col">
                    Vai trò
                  </th>
                  <th className="py-3 px-space-md" scope="col">
                    Đăng nhập gần nhất
                  </th>
                  <th className="py-3 px-space-md" scope="col">
                    Trạng thái
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low">
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

          <div className="p-space-md bg-surface-container-lowest flex items-center justify-between">
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
                className="px-space-md py-1 rounded bg-surface-container-low text-on-surface hover:bg-surface-container font-label-sm text-label-sm transition-colors disabled:text-outline disabled:cursor-not-allowed"
                disabled={!hasPrev || membersLoading}
                type="button"
                onClick={() =>
                  setOffset((current) => Math.max(0, current - PAGE_SIZE))
                }
              >
                Trước
              </button>
              <button
                className="px-space-md py-1 rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm transition-colors disabled:text-outline disabled:cursor-not-allowed"
                disabled={!hasNext || membersLoading}
                type="button"
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
              >
                Sau
              </button>
            </div>
          </div>
        </div>

        <div className="lg:col-span-4 flex flex-col bg-surface-container-lowest rounded shadow-sm p-space-lg">
          <div className="flex items-center justify-between mb-space-md">
            <div className="flex items-center gap-space-xs">
              <MaterialIcon name="history" className="text-[18px] text-secondary" />
              <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">
                Hoạt động gần đây
              </h2>
            </div>
          </div>
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
            <ul className="flex flex-col divide-y divide-surface-container-low">
              {activity.map((event) => (
                <li key={event.id} className="flex flex-col gap-0.5 py-space-sm">
                  <span className="font-title-sm text-title-sm text-on-surface">
                    {event.actor_display_name
                      ? `${event.actor_display_name} · ${event.title}`
                      : event.title}
                  </span>
                  <span className="font-body-sm text-body-sm text-secondary">
                    {formatWhen(event.occurred_at)}
                  </span>
                  {event.detail ? (
                    <span className="font-body-sm text-body-sm text-secondary truncate">
                      {event.detail}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
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
    <div className="bg-surface-container-lowest p-space-lg rounded shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between text-secondary">
        <span className="font-label-sm text-label-sm tracking-wider uppercase">
          Dung lượng
        </span>
        <MaterialIcon name="cloud_done" className="text-[20px] text-secondary" />
      </div>
      {storage ? (
        <div className="mt-space-md">
          <span className="font-display-lg text-display-lg text-on-surface font-semibold">
            {formatBytes(used)}
          </span>
          {percent !== null ? (
            <div className="mt-space-sm">
              <div className="h-1.5 rounded bg-surface-container overflow-hidden">
                <div className="h-full bg-secondary" style={{ width: `${percent}%` }} />
              </div>
              <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
                {percent}% của {formatBytes(quota ?? 0)}
              </p>
            </div>
          ) : (
            <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
              Tổng dung lượng tệp đã tải lên.
            </p>
          )}
        </div>
      ) : (
        <div className="mt-space-md">
          <span className="font-headline-md text-headline-md text-secondary font-semibold">
            Chưa có số liệu
          </span>
          <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
            {emptyNote}
          </p>
        </div>
      )}
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
  to,
}: {
  icon: string
  label: string
  value: string
  to?: string
}) {
  const body = (
    <>
      <div className="flex items-center justify-between text-secondary">
        <span className="font-label-sm text-label-sm tracking-wider uppercase">
          {label}
        </span>
        <MaterialIcon name={icon} className="text-[20px] text-secondary" />
      </div>
      <div className="mt-space-md flex items-baseline justify-between">
        <span className="font-display-lg text-display-lg text-on-surface font-semibold">
          {value}
        </span>
      </div>
    </>
  )
  const className =
    'bg-surface-container-lowest p-space-lg rounded shadow-sm flex flex-col justify-between'
  if (!to) {
    return <div className={className}>{body}</div>
  }
  return (
    <Link
      className={`${className} hover:bg-surface-container-low transition-colors`}
      to={to}
    >
      {body}
    </Link>
  )
}

function MemberRow({ member }: { member: ManagedUser }) {
  const muted = member.status === 'disabled' || member.status === 'invited'
  return (
    <tr className="hover:bg-surface-container-low/60 transition-colors">
      <td className="py-3.5 px-space-lg">
        <div className="flex items-center gap-space-md">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center font-title-sm text-title-sm font-semibold shrink-0 ${
              member.role === 'ADMINISTRATOR'
                ? 'bg-primary-container text-on-primary'
                : 'bg-surface-container text-secondary'
            } ${muted ? 'opacity-60' : ''}`}
          >
            {initials(member.display_name, member.email)}
          </div>
          <div className="flex flex-col min-w-0">
            <span
              className={`font-title-sm text-title-sm text-on-surface truncate ${
                muted ? 'opacity-75' : ''
              }`}
            >
              {member.display_name}
            </span>
            <span className="font-body-sm text-body-sm text-secondary truncate">
              {member.email}
            </span>
          </div>
        </div>
      </td>
      <td className="py-3.5 px-space-md">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded font-label-sm text-label-sm ${
            member.role === 'ADMINISTRATOR'
              ? 'bg-primary-container text-on-primary'
              : 'bg-surface-container text-secondary'
          }`}
        >
          {roleLabel[member.role]}
        </span>
      </td>
      <td className="py-3.5 px-space-md text-secondary">
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
  if (status === 'active') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container text-on-surface font-label-sm text-label-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-secondary" />
        Đang hoạt động
      </span>
    )
  }
  if (status === 'invited') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container-high text-secondary font-label-sm text-label-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-outline" />
        Đã mời
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-error-container text-on-error-container font-label-sm text-label-sm">
      <span className="w-1.5 h-1.5 rounded-full bg-error" />
      Đã khóa
    </span>
  )
}
