import {
  useEffect,
  useId,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import { ApiError } from '../api/client'
import { MaterialIcon } from '../components/icons'
import {
  createUser,
  listUsers,
  resendUserInvite,
  setUserEnabled,
  updateUserRole,
  userAdminErrorMessage,
  type ManagedUser,
  type ManagedUserRole,
  type ManagedUserStatus,
} from '../api/users'
import { useAuth } from '../auth/useAuth'
import { validateWorkEmail } from '../auth/session'
import { usePageTitle } from '../hooks/usePageTitle'

const PAGE_SIZE = 20

const roleOptions: {
  value: ManagedUserRole
  label: string
  hint: string
}[] = [
  {
    value: 'OPERATOR',
    label: 'Vận hành',
    hint: 'Tạo hồ sơ và tải tài liệu. Dùng giao diện người dùng.',
  },
  {
    value: 'REVIEWER',
    label: 'Thẩm định',
    hint: 'Rà soát trích dẫn và xung đột. Dùng giao diện người dùng.',
  },
  {
    value: 'ADMINISTRATOR',
    label: 'Quản trị',
    hint: 'Quản lý người dùng và toàn bộ hệ thống.',
  },
]

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

function sameAccount(user: ManagedUser, email: string | undefined) {
  return Boolean(email) && user.email.toLowerCase() === email?.toLowerCase()
}

export function UsersPage() {
  usePageTitle('Người dùng & Phân quyền')
  const { user: sessionUser } = useAuth()
  const [queryInput, setQueryInput] = useState('')
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<'all' | ManagedUserRole>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | ManagedUserStatus>(
    'all',
  )
  const [offset, setOffset] = useState(0)
  const [reloadKey, setReloadKey] = useState(0)
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [lockTarget, setLockTarget] = useState<ManagedUser | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(queryInput.trim())
      setOffset(0)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [queryInput])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)

    listUsers({
      q: query || undefined,
      role: roleFilter === 'all' ? undefined : roleFilter,
      status: statusFilter === 'all' ? undefined : statusFilter,
      limit: PAGE_SIZE,
      offset,
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return
        setUsers(result.users)
        setTotal(result.total)
      })
      .catch((err: unknown) => {
        const message = userAdminErrorMessage(err)
        if (!message || controller.signal.aborted) return
        setUsers([])
        setTotal(0)
        setError(message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [query, roleFilter, statusFilter, offset, reloadKey])

  const from = users.length === 0 ? 0 : offset + 1
  const to = offset + users.length
  const hasPrev = offset > 0
  const hasNext = offset + PAGE_SIZE < total

  function applyUser(next: ManagedUser) {
    const hiddenByRole = roleFilter !== 'all' && next.role !== roleFilter
    const hiddenByStatus =
      statusFilter !== 'all' && next.status !== statusFilter
    if (hiddenByRole || hiddenByStatus) {
      setUsers((current) => current.filter((item) => item.id !== next.id))
      setTotal((current) => Math.max(0, current - 1))
      return
    }
    setUsers((current) =>
      current.map((item) => (item.id === next.id ? next : item)),
    )
  }

  async function changeRole(target: ManagedUser, role: ManagedUserRole) {
    if (role === target.role || pendingId) return
    setPendingId(target.id)
    setError(null)
    setNotice(null)
    try {
      const updated = await updateUserRole(target.id, role)
      applyUser(updated)
      setNotice(
        `Đã đổi vai trò của ${updated.display_name} thành ${roleLabel[updated.role]}.`,
      )
    } catch (err) {
      const message = userAdminErrorMessage(err)
      if (message) setError(message)
    } finally {
      setPendingId(null)
    }
  }

  async function resend(target: ManagedUser) {
    if (pendingId) return
    setPendingId(target.id)
    setError(null)
    setNotice(null)
    try {
      const updated = await resendUserInvite(target.id)
      applyUser(updated)
      setNotice(`Đã gửi lại email đặt mật khẩu tới ${updated.email}.`)
    } catch (err) {
      const message = userAdminErrorMessage(err)
      if (message) setError(message)
    } finally {
      setPendingId(null)
    }
  }

  async function confirmLock() {
    if (!lockTarget || pendingId) return
    const target = lockTarget
    const enabling = target.status === 'disabled'
    setPendingId(target.id)
    setError(null)
    setNotice(null)
    try {
      const updated = await setUserEnabled(target.id, enabling)
      applyUser(updated)
      setLockTarget(null)
      setNotice(
        enabling
          ? `Đã mở khóa ${updated.display_name}.`
          : `Đã khóa ${updated.display_name}.`,
      )
    } catch (err) {
      const message = userAdminErrorMessage(err)
      if (message) setError(message)
    } finally {
      setPendingId(null)
    }
  }

  return (
    <div className="flex flex-col w-full gap-space-lg">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-md">
        <div className="flex flex-col gap-space-xs">
          <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
            Người dùng & Phân quyền
          </h1>
          <p className="font-body-sm text-body-sm text-secondary max-w-2xl">
            Tạo tài khoản và gán vai trò. Người dùng tự đặt mật khẩu qua email,
            rồi đăng nhập SSO.
          </p>
        </div>
        <button
          className="flex items-center gap-space-xs px-space-lg py-2 rounded bg-primary-container text-on-primary hover:bg-inverse-surface transition-colors shadow-sm font-label-md text-label-md self-start md:self-auto"
          type="button"
          onClick={() => setCreateOpen(true)}
        >
          <MaterialIcon name="person_add" className="text-[18px]" />
          <span>Tạo người dùng</span>
        </button>
      </div>

      <div className="w-full bg-surface-container-low px-space-lg py-space-md rounded flex items-center gap-space-md">
        <div className="w-7 h-7 rounded bg-surface-container flex items-center justify-center shrink-0">
          <MaterialIcon
            name="mark_email_unread"
            className="text-secondary text-[16px]"
          />
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          <strong className="font-title-sm text-title-sm text-on-surface">
            Vận hành và Thẩm định
          </strong>{' '}
          dùng chung giao diện người dùng. Quản trị vào giao diện này.
        </p>
      </div>

      {notice ? (
        <div className="px-space-lg py-space-md rounded bg-surface-container text-on-surface font-body-sm text-body-sm flex items-start justify-between gap-space-md">
          <span>{notice}</span>
          <button
            className="text-secondary hover:text-on-surface"
            type="button"
            aria-label="Đóng thông báo"
            onClick={() => setNotice(null)}
          >
            <MaterialIcon name="close" className="text-[18px]" />
          </button>
        </div>
      ) : null}

      <div className="flex flex-col bg-surface-container-lowest rounded shadow-sm overflow-hidden">
        <div className="p-space-lg flex flex-col lg:flex-row lg:items-center justify-between gap-space-md">
          <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">
            Danh sách người dùng
          </h2>
          <div className="flex items-center gap-space-sm flex-wrap">
            <div className="relative flex items-center">
              <MaterialIcon
                name="search"
                className="absolute left-2.5 text-secondary text-[16px]"
              />
              <input
                className="pl-8 pr-space-md py-1.5 bg-surface-container text-on-surface rounded font-body-sm text-body-sm placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-1 focus:ring-secondary w-52 sm:w-64"
                placeholder="Tìm theo tên, email..."
                type="search"
                value={queryInput}
                onChange={(event) => setQueryInput(event.target.value)}
              />
            </div>
            <FilterSelect
              label="Vai trò"
              value={roleFilter}
              onChange={(value) => {
                setRoleFilter(value as 'all' | ManagedUserRole)
                setOffset(0)
              }}
              options={[
                { value: 'all', label: 'Tất cả vai trò' },
                ...roleOptions.map((role) => ({
                  value: role.value,
                  label: role.label,
                })),
              ]}
            />
            <FilterSelect
              label="Trạng thái"
              value={statusFilter}
              onChange={(value) => {
                setStatusFilter(value as 'all' | ManagedUserStatus)
                setOffset(0)
              }}
              options={[
                { value: 'all', label: 'Tất cả trạng thái' },
                { value: 'invited', label: 'Đã mời' },
                { value: 'active', label: 'Đang hoạt động' },
                { value: 'disabled', label: 'Đã khóa' },
              ]}
            />
          </div>
        </div>

        {error ? (
          <div className="mx-space-lg mb-space-md px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm">
            {error}
          </div>
        ) : null}

        <div className="w-full overflow-x-auto">
          <table className="w-full text-left text-on-surface font-body-sm text-body-sm min-w-[880px]">
            <thead>
              <tr className="bg-surface-container-low text-secondary font-label-sm text-label-sm uppercase tracking-wider">
                <th className="py-3 px-space-lg" scope="col">
                  Người dùng
                </th>
                <th className="py-3 px-space-md" scope="col">
                  Vai trò
                </th>
                <th className="py-3 px-space-md" scope="col">
                  Trạng thái
                </th>
                <th className="py-3 px-space-md" scope="col">
                  Đăng nhập gần nhất
                </th>
                <th className="py-3 px-space-md text-right" scope="col">
                  Thao tác
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-low">
              {loading && users.length === 0 ? (
                <tr>
                  <td className="py-10 px-space-lg text-secondary" colSpan={5}>
                    Đang tải danh sách người dùng…
                  </td>
                </tr>
              ) : null}
              {!loading && users.length === 0 ? (
                <tr>
                  <td className="py-12 px-space-lg" colSpan={5}>
                    <div className="flex flex-col items-center gap-space-sm text-center">
                      <MaterialIcon
                        name="group"
                        className="text-secondary text-[28px]"
                      />
                      <p className="font-title-sm text-title-sm text-on-surface">
                        {error
                          ? 'Chưa tải được danh sách'
                          : 'Chưa có người dùng khớp bộ lọc'}
                      </p>
                      <p className="font-body-sm text-body-sm text-secondary max-w-md">
                        {error
                          ? 'Form tạo user vẫn mở được. Danh sách hiện khi backend có API quản lý người dùng.'
                          : 'Tạo người dùng để gửi email đặt mật khẩu.'}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : null}
              {users.map((member) => (
                <UserRow
                  key={member.id}
                  member={member}
                  busy={pendingId === member.id || loading}
                  self={sameAccount(member, sessionUser?.email)}
                  onRole={(role) => changeRole(member, role)}
                  onResend={() => resend(member)}
                  onLock={() => setLockTarget(member)}
                />
              ))}
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
            người dùng
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

      {createOpen ? (
        <CreateUserDialog
          onClose={() => setCreateOpen(false)}
          onCreated={(created) => {
            setCreateOpen(false)
            setNotice(`Đã gửi lời mời đặt mật khẩu tới ${created.email}.`)
            setOffset(0)
            setReloadKey((current) => current + 1)
          }}
          onEmailExists={() => {
            setOffset(0)
            setReloadKey((current) => current + 1)
          }}
        />
      ) : null}

      {lockTarget ? (
        <ConfirmDialog
          title={
            lockTarget.status === 'disabled'
              ? 'Mở khóa người dùng'
              : 'Khóa người dùng'
          }
          body={
            lockTarget.status === 'disabled'
              ? `${lockTarget.display_name} đăng nhập lại được bằng SSO.`
              : `${lockTarget.display_name} không đăng nhập được cho đến khi mở khóa.`
          }
          confirmLabel={lockTarget.status === 'disabled' ? 'Mở khóa' : 'Khóa'}
          busy={pendingId === lockTarget.id}
          onClose={() => {
            if (pendingId !== lockTarget.id) setLockTarget(null)
          }}
          onConfirm={confirmLock}
        />
      ) : null}
    </div>
  )
}

function UserRow({
  member,
  busy,
  self,
  onRole,
  onResend,
  onLock,
}: {
  member: ManagedUser
  busy: boolean
  self: boolean
  onRole: (role: ManagedUserRole) => void
  onResend: () => void
  onLock: () => void
}) {
  const muted = member.status === 'disabled' || member.status === 'invited'
  const locking = member.status !== 'disabled'

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
        <div className="relative inline-flex">
          <label className="sr-only" htmlFor={`role-${member.id}`}>
            Vai trò của {member.display_name}
          </label>
          <select
            id={`role-${member.id}`}
            className="appearance-none bg-surface-container text-on-surface font-body-sm text-body-sm py-1.5 pl-3 pr-8 rounded focus:outline-none focus:ring-1 focus:ring-secondary disabled:opacity-60 disabled:cursor-not-allowed"
            value={member.role}
            disabled={busy || self}
            title={self ? 'Không đổi vai trò của chính bạn' : 'Đổi vai trò'}
            onChange={(event) => onRole(event.target.value as ManagedUserRole)}
          >
            {roleOptions.map((role) => (
              <option key={role.value} value={role.value}>
                {role.label}
              </option>
            ))}
          </select>
          <MaterialIcon
            name="expand_more"
            className="absolute right-2 top-2 pointer-events-none text-secondary text-[16px]"
          />
        </div>
      </td>
      <td className="py-3.5 px-space-md">
        <StatusBadge status={member.status} />
      </td>
      <td className="py-3.5 px-space-md text-secondary">
        {member.status === 'invited'
          ? 'Chưa đăng nhập'
          : formatWhen(member.last_login_at)}
      </td>
      <td className="py-3.5 px-space-md">
        <div className="flex items-center justify-end gap-space-xs">
          {member.status === 'invited' ? (
            <button
              className="h-8 px-space-sm rounded flex items-center gap-1 text-secondary hover:bg-surface-container hover:text-on-surface transition-colors font-label-sm text-label-sm disabled:opacity-50"
              type="button"
              disabled={busy}
              onClick={onResend}
            >
              <MaterialIcon name="forward_to_inbox" className="text-[16px]" />
              Gửi lại
            </button>
          ) : null}
          <button
            className="h-8 px-space-sm rounded flex items-center gap-1 text-secondary hover:bg-surface-container hover:text-on-surface transition-colors font-label-sm text-label-sm disabled:opacity-50"
            type="button"
            disabled={busy || self}
            title={self ? 'Không khóa tài khoản đang đăng nhập' : undefined}
            onClick={onLock}
          >
            <MaterialIcon
              name={locking ? 'lock' : 'lock_open'}
              className="text-[16px]"
            />
            {locking ? 'Khóa' : 'Mở khóa'}
          </button>
        </div>
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

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  return (
    <div className="relative">
      <select
        aria-label={label}
        className="appearance-none bg-surface-container text-on-surface font-body-sm text-body-sm py-1.5 pl-3 pr-8 rounded focus:outline-none cursor-pointer"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <MaterialIcon
        name="expand_more"
        className="absolute right-2 top-2 pointer-events-none text-secondary text-[16px]"
      />
    </div>
  )
}

function CreateUserDialog({
  onClose,
  onCreated,
  onEmailExists,
}: {
  onClose: () => void
  onCreated: (user: ManagedUser) => void
  onEmailExists: () => void
}) {
  const titleId = useId()
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState<ManagedUserRole>('OPERATOR')
  const [nameError, setNameError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape' && !saving) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, saving])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving) return
    let normalized = ''
    try {
      normalized = validateWorkEmail(email)
    } catch (err) {
      setNameError(null)
      setFieldError(err instanceof Error ? err.message : 'Email không hợp lệ.')
      return
    }
    const nameField = event.currentTarget.elements.namedItem('displayName')
    const typedName = nameField instanceof HTMLInputElement ? nameField.value : name
    const displayName = typedName.trim()
    if (!displayName) {
      setFieldError(null)
      setNameError('Nhập tên người dùng.')
      return
    }
    if (displayName.length > 255) {
      setFieldError(null)
      setNameError('Tên tối đa 255 ký tự.')
      return
    }
    setNameError(null)
    setFieldError(null)
    setSaving(true)
    try {
      const created = await createUser({
        email: normalized,
        display_name: displayName,
        role,
      })
      onCreated(created)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'email_exists') {
        onEmailExists()
      }
      setFieldError(userAdminErrorMessage(err) ?? 'Không gửi được lời mời.')
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center px-space-md py-space-lg bg-primary/40">
      <form
        className="w-full max-w-lg bg-surface-container-lowest rounded shadow-sm p-space-lg flex flex-col gap-space-lg max-h-full overflow-y-auto"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        autoComplete="off"
        onSubmit={submit}
      >
        <div className="flex items-start justify-between gap-space-md">
          <div className="flex flex-col gap-space-xs">
            <h2
              id={titleId}
              className="font-headline-md text-headline-md text-on-surface"
            >
              Tạo người dùng
            </h2>
            <p className="font-body-sm text-body-sm text-secondary">
              Hệ thống gửi email để người này tự đặt mật khẩu.
            </p>
          </div>
          <button
            className="w-8 h-8 rounded flex items-center justify-center text-secondary hover:bg-surface-container hover:text-on-surface"
            type="button"
            aria-label="Đóng"
            onClick={onClose}
            disabled={saving}
          >
            <MaterialIcon name="close" className="text-[18px]" />
          </button>
        </div>

        <div className="flex flex-col gap-space-md">
          <Field label="Email" htmlFor="new-user-email">
            <input
              id="new-user-email"
              className="h-10 px-space-md bg-surface text-on-surface font-body-sm text-body-sm rounded focus:outline-none focus:ring-2 focus:ring-on-tertiary-container focus:bg-surface-container-lowest"
              type="email"
              autoComplete="off"
              autoFocus
              placeholder="ten@congty.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </Field>
          <Field label="Tên (bắt buộc)" htmlFor="new-user-name">
            <input
              id="new-user-name"
              name="displayName"
              className={`h-10 px-space-md bg-surface text-on-surface font-body-sm text-body-sm rounded focus:outline-none focus:ring-2 focus:bg-surface-container-lowest ${
                nameError
                  ? 'ring-2 ring-error focus:ring-error'
                  : 'focus:ring-on-tertiary-container'
              }`}
              type="text"
              autoComplete="off"
              placeholder="Họ và tên"
              aria-invalid={nameError ? true : undefined}
              aria-describedby={nameError ? 'new-user-name-error' : undefined}
              value={name}
              onChange={(event) => {
                setName(event.target.value)
                if (nameError) setNameError(null)
              }}
            />
            {nameError ? (
              <p id="new-user-name-error" className="font-body-sm text-body-sm text-error" role="alert">
                {nameError}
              </p>
            ) : null}
          </Field>
          <fieldset className="flex flex-col gap-space-sm">
            <legend className="font-label-sm text-label-sm text-secondary tracking-wider uppercase">
              Vai trò
            </legend>
            {roleOptions.map((option) => (
              <label
                key={option.value}
                className={`flex items-start gap-space-md px-space-md py-space-sm rounded cursor-pointer border ${
                  role === option.value
                    ? 'bg-surface-container-low border-primary-container'
                    : 'bg-surface border-transparent hover:bg-surface-container-low'
                }`}
              >
                <input
                  className="mt-1"
                  type="radio"
                  name="role"
                  value={option.value}
                  checked={role === option.value}
                  onChange={() => setRole(option.value)}
                />
                <span className="flex flex-col">
                  <span className="font-title-sm text-title-sm text-on-surface">
                    {option.label}
                  </span>
                  <span className="font-body-sm text-body-sm text-secondary">
                    {option.hint}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
        </div>

        {fieldError ? (
          <p className="font-body-sm text-body-sm text-error" role="alert">
            {fieldError}
          </p>
        ) : null}

        <div className="flex items-center justify-end gap-space-sm">
          <button
            className="px-space-md py-2 rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-label-md text-label-md"
            type="button"
            onClick={onClose}
            disabled={saving}
          >
            Hủy
          </button>
          <button
            className="px-space-lg py-2 rounded bg-primary-container text-on-primary hover:bg-inverse-surface font-label-md text-label-md disabled:opacity-70"
            type="submit"
            disabled={saving}
          >
            {saving ? 'Đang gửi…' : 'Gửi lời mời'}
          </button>
        </div>
      </form>
    </div>
  )
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-space-xs">
      <label
        className="font-label-sm text-label-sm text-secondary tracking-wider uppercase"
        htmlFor={htmlFor}
      >
        {label}
      </label>
      {children}
    </div>
  )
}

function ConfirmDialog({
  title,
  body,
  confirmLabel,
  busy,
  onClose,
  onConfirm,
}: {
  title: string
  body: string
  confirmLabel: string
  busy: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  const titleId = useId()

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape' && !busy) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, onClose])

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center px-space-md bg-primary/40">
      <div
        className="w-full max-w-md bg-surface-container-lowest rounded shadow-sm p-space-lg flex flex-col gap-space-md"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <h2
          id={titleId}
          className="font-headline-md text-headline-md text-on-surface"
        >
          {title}
        </h2>
        <p className="font-body-sm text-body-sm text-secondary">{body}</p>
        <div className="flex items-center justify-end gap-space-sm">
          <button
            className="px-space-md py-2 rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-label-md text-label-md"
            type="button"
            onClick={onClose}
            disabled={busy}
          >
            Hủy
          </button>
          <button
            className="px-space-lg py-2 rounded bg-primary-container text-on-primary hover:bg-inverse-surface font-label-md text-label-md disabled:opacity-70"
            type="button"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? 'Đang xử lý…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
