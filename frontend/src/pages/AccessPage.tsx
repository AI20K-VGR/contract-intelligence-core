import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import {
  listDossiers,
  listDossiersErrorMessage,
  updateDossierAccess,
} from '../api/dossiers'
import { listUsers, type ManagedUser } from '../api/users'
import { homePath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { dossierOpenTo, type Dossier } from '../data/dossiers'
import { usePageTitle } from '../hooks/usePageTitle'
import {
  formatExpiry,
  fromDateInput,
  grantEffect,
  grantPermission,
  isGrantExpired,
  permissionLabels,
  shareRoleLabels,
  todayInput,
  toDateInput,
  type SharePermission,
  type ShareRole,
} from '../data/shareGrant'
import { dossierFromSummary } from './MyDossiersPage'

type AccessFilter = 'all' | Dossier['access']

type GrantOption = { permission: SharePermission; expires: string }

const DEFAULT_OPTION: GrantOption = { permission: 'read', expires: '' }

const filters: { id: AccessFilter; label: string; dot?: string }[] = [
  { id: 'all', label: 'Tất cả' },
  { id: 'mine', label: 'Hồ sơ của tôi', dot: 'bg-emerald-600' },
  { id: 'shared_out', label: 'Hồ sơ đã chia sẻ', dot: 'bg-amber-500' },
  { id: 'shared_in', label: 'Hồ sơ được chia sẻ', dot: 'bg-[#2563eb]' },
]

export function AccessPage() {
  const { user } = useAuth()
  const sharedOnly = user?.backendRole !== 'ADMINISTRATOR'
  usePageTitle('Quyền truy cập')
  const [params, setParams] = useSearchParams()
  const selectedId = params.get('dossier')
  const [dossiers, setDossiers] = useState<Dossier[]>([])
  const [people, setPeople] = useState<ManagedUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<AccessFilter>(
    sharedOnly ? 'shared_in' : 'all',
  )
  const [chosen, setChosen] = useState<string[]>([])
  const [options, setOptions] = useState<Record<string, GrantOption>>({})
  const [savingId, setSavingId] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ text: string; icon: string } | null>(
    null,
  )

  const selected = dossiers.find((item) => item.id === selectedId) ?? null
  const tenants = people.filter((person) => person.id !== user?.id)
  const visible = useMemo(
    () =>
      filter === 'all'
        ? dossiers
        : dossiers.filter((item) => item.access === filter),
    [dossiers, filter],
  )

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    listDossiers({ limit: 100, offset: 0, signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return
        setDossiers(
          result.items.map((item) =>
            dossierFromSummary(item, user?.id, user?.email),
          ),
        )
        setError(null)
      })
      .catch((cause: unknown) => {
        const message = listDossiersErrorMessage(cause)
        if (message && !controller.signal.aborted) setError(message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    listUsers({ limit: 100, offset: 0, signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setPeople(result.users)
      })
      .catch(() => {
        if (!controller.signal.aborted) setPeople([])
      })
    return () => controller.abort()
  }, [user?.id, user?.email])

  useEffect(() => {
    setChosen(selected?.shares?.map((item) => item.id) ?? [])
    setOptions(
      Object.fromEntries(
        (selected?.shares ?? []).map((item) => [
          item.id,
          {
            permission: grantPermission(item),
            expires: toDateInput(item.expires_at),
          },
        ]),
      ),
    )
    setSaveError(null)
  }, [selected])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 5000)
    return () => window.clearTimeout(timer)
  }, [notice])

  function select(id: string) {
    setParams({ dossier: id })
  }

  async function saveAccess(
    dossier: Dossier,
    nextScope: Dossier['access'],
    shareIds: string[],
    shareOptions: Record<string, GrantOption> = {},
  ) {
    setSavingId(dossier.id)
    setSaveError(null)
    const shares =
      nextScope === 'mine'
        ? []
        : people
            .filter((person) => shareIds.includes(person.id))
            .map((person) => ({
              id: person.id,
              email: person.email,
              display_name: person.display_name,
              status: person.status,
              permission: (shareOptions[person.id] ?? DEFAULT_OPTION)
                .permission,
              expires_at: fromDateInput(
                (shareOptions[person.id] ?? DEFAULT_OPTION).expires,
              ),
            }))
    try {
      const saved = await updateDossierAccess(dossier.id, nextScope, shares)
      setDossiers((current) =>
        current.map((item) =>
          item.id === dossier.id
            ? { ...item, access: saved.scope, shares: saved.shared_with }
            : item,
        ),
      )
      setChosen(saved.shared_with.map((item) => item.id))
      // Đóng hộp và báo đã lưu để người dùng biết thao tác thành công.
      setParams({})
      setNotice({
        text:
          nextScope === 'mine'
            ? 'Đã đổi thành hồ sơ của bạn, không còn chia sẻ.'
            : 'Đã lưu quyền truy cập.',
        icon: 'check_circle',
      })
    } catch (cause: unknown) {
      setSaveError(
        cause instanceof ApiError && cause.message
          ? cause.message
          : 'Chưa lưu được quyền truy cập.',
      )
    } finally {
      setSavingId(null)
    }
  }

  if (user?.backendRole === 'REVIEWER') {
    return <Navigate to={homePath(user.role)} replace />
  }

  const shownFilters = sharedOnly
    ? filters.filter((item) => item.id === 'shared_in')
    : filters
  const columnCount = sharedOnly ? 5 : 6

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <p className="font-body-sm text-body-sm text-on-surface-variant pb-space-lg">
        {sharedOnly
          ? 'Hồ sơ người khác chia sẻ cho bạn.'
          : 'Phân loại hồ sơ bạn tải lên, hồ sơ bạn đã chia sẻ và hồ sơ người khác chia sẻ cho bạn.'}
      </p>

      <div className="bg-surface-container-lowest rounded-lg shadow-[0_1px_3px_rgba(15,23,42,0.06)] flex flex-col">
        <div className="p-space-md bg-surface-container-lowest">
          <div className="inline-flex items-center bg-surface-container-low p-1 rounded-lg gap-1 flex-wrap">
            {shownFilters.map((item) => {
              const active = filter === item.id
              const count =
                item.id === 'all'
                  ? dossiers.length
                  : dossiers.filter((row) => row.access === item.id).length
              return (
                <button
                  key={item.id}
                  className={`px-3 py-1 rounded font-label-sm text-label-sm uppercase tracking-wide flex items-center gap-1.5 transition-colors ${
                    active
                      ? 'bg-surface-container-lowest text-on-surface shadow-sm font-semibold'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                  type="button"
                  onClick={() => setFilter(item.id)}
                >
                  {item.dot ? (
                    <span className={`w-1.5 h-1.5 rounded-full ${item.dot}`} />
                  ) : null}
                  <span>{item.label}</span>
                  <span
                    className={`font-code-sm text-[11px] ${
                      item.id === 'all' && active
                        ? 'text-on-surface-variant'
                        : ''
                    }`}
                  >
                    {count}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        <div className="w-full">
          {/* table-fixed: chữ dài bị cắt "…" thay vì đẩy bảng tràn ngang. */}
          <table className="w-full table-fixed text-left font-body-sm text-body-sm border-collapse">
            <thead>
              <tr className="bg-surface-container-low text-on-secondary-container font-label-sm text-label-sm uppercase tracking-wider">
                <th className="py-3 px-3 font-semibold">Hồ sơ</th>
                <th className="py-3 px-3 font-semibold w-[8.5rem]">
                  Phân loại
                </th>
                <th className="py-3 px-3 font-semibold">Người có quyền</th>
                <th className="py-3 px-3 font-semibold w-[9rem]">
                  Quyền · Hạn
                </th>
                <th className="hidden xl:table-cell py-3 px-3 font-semibold w-[7.5rem]">
                  Tải lên
                </th>
                {sharedOnly ? null : (
                  <th className="py-3 px-3 font-semibold text-right w-[10rem]">
                    Thao tác
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-low text-on-surface">
              {error ? (
                <tr>
                  <td
                    className="py-10 px-space-md text-error"
                    colSpan={columnCount}
                  >
                    {error}
                  </td>
                </tr>
              ) : null}
              {loading && dossiers.length === 0 ? (
                <tr>
                  <td
                    className="py-10 px-space-md text-on-surface-variant"
                    colSpan={columnCount}
                  >
                    Đang tải danh sách hồ sơ…
                  </td>
                </tr>
              ) : null}
              {!loading && !error && visible.length === 0 ? (
                <tr>
                  <td
                    className="py-10 px-space-md text-on-surface-variant"
                    colSpan={columnCount}
                  >
                    Không có hồ sơ trong nhóm này.
                  </td>
                </tr>
              ) : null}
              {visible.map((item) => {
                const active = item.id === selectedId
                return (
                  <tr
                    key={item.id}
                    className={`transition-colors ${
                      active
                        ? 'bg-surface-container'
                        : 'bg-surface-container-lowest hover:bg-surface-container-low/70'
                    }`}
                  >
                    <td className="py-3.5 px-3 align-top">
                      {item.myGrant?.expired ? (
                        <span
                          className="block truncate font-title-sm text-title-sm font-semibold text-on-surface-variant"
                          title={`${item.title} · Quyền chia sẻ đã hết hạn`}
                        >
                          {item.title}
                        </span>
                      ) : (
                        <Link
                          className="block truncate font-title-sm text-title-sm font-semibold text-on-surface hover:text-on-tertiary-container"
                          state={{ dossierId: item.id, name: item.title }}
                          title={item.title}
                          to={dossierOpenTo(item)}
                        >
                          {item.title}
                        </Link>
                      )}
                      <span
                        className="block truncate font-code-sm text-label-sm text-on-surface-variant mt-1"
                        title={item.code}
                      >
                        {item.code}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 align-top">
                      <AccessTag access={item.access} />
                      {pendingInvite(item, user?.id, user?.email) ? (
                        <button
                          className="mt-1.5 flex whitespace-nowrap items-center gap-1 rounded bg-amber-50 px-2 py-0.5 font-label-sm text-label-sm text-amber-900 hover:bg-amber-100"
                          type="button"
                          onClick={() =>
                            setNotice({
                              text: 'Vui lòng kiểm tra mail mời rồi làm theo hướng dẫn.',
                              icon: 'mark_email_unread',
                            })
                          }
                        >
                          <MaterialIcon
                            name="mark_email_unread"
                            className="text-[14px]"
                          />
                          Chưa nhận mời
                        </button>
                      ) : null}
                    </td>
                    <td className="py-3.5 px-3 align-top">
                      <PeopleCell
                        access={item.access}
                        rows={grantRows(item, user, people)}
                      />
                    </td>
                    <td className="py-3.5 px-3 align-top">
                      <GrantCell rows={grantRows(item, user, people)} />
                    </td>
                    <td className="hidden xl:table-cell py-3.5 px-3 align-top text-on-surface-variant">
                      <span className="flex h-10 items-center truncate">
                        {item.updated || '—'}
                      </span>
                    </td>
                    {sharedOnly ? null : (
                      <td className="py-3.5 px-3 align-top text-right">
                        {item.access === 'shared_in' ? (
                          <span className="flex h-10 items-center justify-end font-body-sm text-body-sm text-on-surface-variant">
                            —
                          </span>
                        ) : (
                          <div className="relative inline-flex items-center justify-end gap-1.5">
                            <button
                              className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 font-label-md text-label-md font-semibold disabled:opacity-50 ${
                                active
                                  ? 'bg-brand-200 text-brand-800'
                                  : 'bg-brand-100 text-brand-700 hover:bg-brand-200'
                              }`}
                              disabled={savingId === item.id}
                              type="button"
                              onClick={() => select(active ? '' : item.id)}
                            >
                              <MaterialIcon
                                name="person_add"
                                className="text-[18px]"
                              />
                              Chia sẻ
                            </button>
                            {item.access === 'shared_out' ? (
                              <button
                                aria-label="Ngừng chia sẻ"
                                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-outline-variant bg-white hover:bg-surface-container-low disabled:opacity-50"
                                disabled={savingId === item.id}
                                title="Ngừng chia sẻ: thu hồi quyền của mọi người"
                                type="button"
                                onClick={() => {
                                  if (
                                    !window.confirm(
                                      'Ngừng chia sẻ hồ sơ này? Mọi người được chia sẻ sẽ mất quyền truy cập.',
                                    )
                                  ) {
                                    return
                                  }
                                  void saveAccess(item, 'mine', [])
                                }}
                              >
                                <MaterialIcon
                                  name={
                                    savingId === item.id
                                      ? 'progress_activity'
                                      : 'link_off'
                                  }
                                  className={`text-[18px] text-error ${
                                    savingId === item.id ? 'animate-spin' : ''
                                  }`}
                                />
                              </button>
                            ) : null}
                            {active ? (
                              <div className="absolute right-0 top-10 z-50 flex text-left w-[26rem] max-w-[calc(100vw-2rem)] flex-col gap-space-sm rounded-lg border border-surface-container bg-surface-container-lowest p-space-md shadow-[0_8px_24px_rgba(15,23,42,0.12)]">
                                <p className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">
                                  Chia sẻ với
                                </p>
                                <AccessLegend />
                                <div className="flex max-h-72 flex-col gap-space-xs overflow-auto">
                                  {tenants.length === 0 ? (
                                    <p className="px-1 font-body-sm text-body-sm text-secondary">
                                      Tenant chưa có người dùng khác.
                                    </p>
                                  ) : (
                                    tenants.map((person) => {
                                      const isChosen = chosen.includes(
                                        person.id,
                                      )
                                      const option =
                                        options[person.id] ?? DEFAULT_OPTION
                                      const pastDate =
                                        Boolean(option.expires) &&
                                        option.expires < todayInput()
                                      return (
                                        <div
                                          key={person.id}
                                          className={`rounded-lg border px-space-sm py-space-sm ${
                                            isChosen
                                              ? 'border-primary-container/30 bg-surface-container-low'
                                              : 'border-transparent hover:bg-surface-container-low'
                                          }`}
                                        >
                                          <label className="flex cursor-pointer items-center gap-space-sm">
                                            <input
                                              checked={isChosen}
                                              className="h-4 w-4 shrink-0"
                                              type="checkbox"
                                              onChange={() =>
                                                setChosen((current) =>
                                                  current.includes(person.id)
                                                    ? current.filter(
                                                        (id) =>
                                                          id !== person.id,
                                                      )
                                                    : [...current, person.id],
                                                )
                                              }
                                            />
                                            <span className="min-w-0 flex-1">
                                              <span className="block truncate font-body-sm text-body-sm font-semibold text-on-surface">
                                                {person.display_name}
                                              </span>
                                              <span className="block truncate font-label-sm text-label-sm text-on-surface-variant">
                                                {person.email}
                                              </span>
                                            </span>
                                            <RoleBadge role={person.role} />
                                          </label>
                                          {isChosen ? (
                                            <div className="mt-space-sm grid grid-cols-2 gap-space-sm pl-7">
                                              <label className="flex flex-col gap-1">
                                                <span className="font-label-sm text-label-sm text-on-surface-variant">
                                                  Quyền
                                                </span>
                                                <select
                                                  aria-label={`Quyền của ${person.display_name}`}
                                                  className="h-9 w-full rounded bg-surface-container-lowest px-2 font-body-sm text-body-sm text-on-surface ring-1 ring-surface-container-high"
                                                  value={option.permission}
                                                  onChange={(event) =>
                                                    setOptions((current) => ({
                                                      ...current,
                                                      [person.id]: {
                                                        ...option,
                                                        permission: event.target
                                                          .value as SharePermission,
                                                      },
                                                    }))
                                                  }
                                                >
                                                  <option value="read">
                                                    {permissionLabels.read}
                                                  </option>
                                                  <option value="edit">
                                                    {permissionLabels.edit}
                                                  </option>
                                                </select>
                                              </label>
                                              <label className="flex flex-col gap-1">
                                                <span className="font-label-sm text-label-sm text-on-surface-variant">
                                                  Hết hạn
                                                </span>
                                                <input
                                                  aria-label={`Ngày hết hạn của ${person.display_name}`}
                                                  className={`h-9 w-full rounded bg-surface-container-lowest px-2 font-body-sm text-body-sm text-on-surface ring-1 ${
                                                    pastDate
                                                      ? 'ring-error'
                                                      : 'ring-surface-container-high'
                                                  }`}
                                                  min={todayInput()}
                                                  type="date"
                                                  value={option.expires}
                                                  onChange={(event) =>
                                                    setOptions((current) => ({
                                                      ...current,
                                                      [person.id]: {
                                                        ...option,
                                                        expires:
                                                          event.target.value,
                                                      },
                                                    }))
                                                  }
                                                />
                                              </label>
                                              <p className="col-span-2 flex items-start gap-1 rounded bg-surface-container-lowest px-2 py-1.5 font-label-sm text-label-sm text-on-surface">
                                                <MaterialIcon
                                                  name="info"
                                                  className="mt-px shrink-0 text-[14px] text-brand-700"
                                                />
                                                {grantEffect(
                                                  person.role,
                                                  option.permission,
                                                )}
                                              </p>
                                              <p
                                                className={`col-span-2 font-label-sm text-label-sm ${
                                                  pastDate
                                                    ? 'text-error'
                                                    : 'text-secondary'
                                                }`}
                                              >
                                                {pastDate
                                                  ? 'Ngày hết hạn đã qua, chọn ngày khác.'
                                                  : option.expires
                                                    ? `Hết hạn hết ngày ${formatExpiry(fromDateInput(option.expires))}.`
                                                    : 'Để trống ngày thì không hết hạn.'}
                                              </p>
                                            </div>
                                          ) : null}
                                        </div>
                                      )
                                    })
                                  )}
                                </div>
                                {saveError ? (
                                  <p className="font-body-sm text-body-sm text-error">
                                    {saveError}
                                  </p>
                                ) : null}
                                <div className="flex gap-space-sm">
                                  <button
                                    className="h-8 px-space-md rounded bg-surface-container-low text-on-surface font-label-sm text-label-sm hover:bg-surface-container disabled:opacity-50"
                                    disabled={savingId === item.id}
                                    type="button"
                                    onClick={() => select('')}
                                  >
                                    Hủy
                                  </button>
                                  <button
                                    className="h-8 flex-1 px-space-sm rounded bg-brand-100 text-brand-700 hover:bg-brand-200 font-label-sm text-label-sm disabled:opacity-50"
                                    disabled={
                                      savingId === item.id ||
                                      chosen.length === 0 ||
                                      chosen.some(
                                        (id) =>
                                          (options[id]?.expires ?? '') !== '' &&
                                          (options[id]?.expires ?? '') <
                                            todayInput(),
                                      )
                                    }
                                    type="button"
                                    onClick={() => {
                                      void saveAccess(
                                        item,
                                        'shared_out',
                                        chosen,
                                        options,
                                      )
                                    }}
                                  >
                                    {savingId === item.id
                                      ? 'Đang lưu…'
                                      : 'Lưu quyền'}
                                  </button>
                                </div>
                              </div>
                            ) : null}
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
      {notice ? (
        <div
          className="fixed top-20 right-6 z-[70] flex w-[min(24rem,calc(100vw-3rem))] items-start gap-space-md rounded border border-surface-container bg-surface-container-lowest px-space-lg py-space-md font-body-sm text-body-sm text-on-surface shadow-md"
          role="status"
        >
          <MaterialIcon
            name={notice.icon}
            className={`shrink-0 text-[20px] ${
              notice.icon === 'check_circle'
                ? 'text-emerald-600'
                : 'text-amber-700'
            }`}
          />
          <span className="flex-1">{notice.text}</span>
          <button
            aria-label="Đóng thông báo"
            className="shrink-0 text-secondary hover:text-on-surface"
            type="button"
            onClick={() => setNotice(null)}
          >
            <MaterialIcon name="close" className="text-[18px]" />
          </button>
        </div>
      ) : null}
    </div>
  )
}

const ACCESS_TAG: Record<
  Dossier['access'],
  { label: string; dot: string; className: string }
> = {
  mine: {
    label: 'Của tôi',
    dot: 'bg-emerald-600',
    className: 'bg-emerald-50 text-emerald-900',
  },
  shared_out: {
    label: 'Đã chia sẻ',
    dot: 'bg-amber-500',
    className: 'bg-amber-50 text-amber-900',
  },
  shared_in: {
    label: 'Được chia sẻ',
    dot: 'bg-[#2563eb]',
    className: 'bg-blue-50 text-blue-900',
  },
}

/** Cùng màu chấm với bộ lọc phía trên. */
function AccessTag({ access }: { access: Dossier['access'] }) {
  const tag = ACCESS_TAG[access]
  return (
    <span
      className={`inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 font-label-sm text-label-sm font-semibold ${tag.className}`}
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tag.dot}`} />
      {tag.label}
    </span>
  )
}

type GrantRow = {
  id: string
  name: string
  email: string
  permission: SharePermission
  role?: ShareRole
  expiresAt: string | null
  expired: boolean
}

/** Mỗi người có quyền trên hồ sơ: người được chia sẻ, hoặc chính bạn ở hồ sơ được chia sẻ. */
function grantRows(
  dossier: Dossier,
  me: { email?: string; backendRole?: ShareRole } | null | undefined,
  people: ManagedUser[],
): GrantRow[] {
  if (dossier.access === 'shared_out') {
    return (dossier.shares ?? []).map((grant) => ({
      id: grant.id,
      name: grant.display_name || grant.email,
      email: grant.email,
      permission: grantPermission(grant),
      role: people.find((person) => person.id === grant.id)?.role,
      expiresAt: grant.expires_at ?? null,
      expired: isGrantExpired(grant),
    }))
  }
  if (dossier.access === 'shared_in' && dossier.myGrant) {
    return [
      {
        id: 'me',
        name: 'Bạn',
        email: me?.email ?? '',
        permission: dossier.myGrant.permission,
        role: me?.backendRole,
        expiresAt: dossier.myGrant.expires_at,
        expired: dossier.myGrant.expired,
      },
    ]
  }
  return []
}

function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  const first = words[0][0] ?? ''
  const last = words.length > 1 ? (words[words.length - 1][0] ?? '') : ''
  return `${first}${last}`.toUpperCase()
}

// Mỗi người một dòng cao h-10 ở cả hai cột để tên và quyền thẳng hàng.
function PeopleCell({
  access,
  rows,
}: {
  access: Dossier['access']
  rows: GrantRow[]
}) {
  if (rows.length === 0) {
    return (
      <span className="flex h-10 items-center font-body-sm text-body-sm text-on-surface-variant">
        {access === 'mine' ? 'Chỉ mình bạn' : '—'}
      </span>
    )
  }
  return (
    <ul className="flex flex-col gap-1">
      {rows.map((row) => (
        <li
          key={row.id}
          className="flex h-10 min-w-0 items-center gap-space-sm"
        >
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-100 font-label-sm text-[11px] font-bold text-brand-700">
            {initials(row.name)}
          </span>
          <span className="min-w-0">
            <span className="block truncate font-body-sm text-body-sm font-semibold text-on-surface">
              {row.name}
            </span>
            {row.email && row.email !== row.name ? (
              <span className="block truncate font-label-sm text-label-sm text-on-surface-variant">
                {row.email}
              </span>
            ) : null}
          </span>
          {row.role ? <RoleBadge role={row.role} /> : null}
        </li>
      ))}
    </ul>
  )
}

function GrantCell({ rows }: { rows: GrantRow[] }) {
  if (rows.length === 0) {
    return (
      <span className="flex h-10 items-center text-on-surface-variant">—</span>
    )
  }
  return (
    <ul className="flex flex-col gap-1">
      {rows.map((row) => (
        <li
          key={row.id}
          className="flex h-10 flex-col items-start justify-center gap-0.5"
        >
          <span
            className="inline-flex shrink-0 cursor-help items-center gap-1 rounded bg-surface-container px-1.5 font-label-sm text-label-sm leading-5 text-on-surface"
            title={grantEffect(row.role, row.permission)}
          >
            <MaterialIcon
              name={row.permission === 'read' ? 'visibility' : 'edit'}
              className="text-[14px]"
            />
            {permissionLabels[row.permission]}
          </span>
          <span
            className={`whitespace-nowrap font-label-sm text-[11px] leading-4 ${
              row.expired
                ? 'font-semibold text-error'
                : 'text-on-surface-variant'
            }`}
          >
            {row.expired
              ? 'Đã hết hạn'
              : row.expiresAt
                ? `Đến ${formatExpiry(row.expiresAt)}`
                : 'Không hết hạn'}
          </span>
        </li>
      ))}
    </ul>
  )
}

function RoleBadge({ role }: { role: ShareRole }) {
  return (
    <span className="shrink-0 rounded-full bg-brand-50 px-2 font-label-sm text-[11px] font-semibold leading-5 text-brand-700">
      {shareRoleLabels[role]}
    </span>
  )
}

/** Quyền chia sẻ chỉ mở hồ sơ; việc làm được còn tùy vai trò của người nhận. */
function AccessLegend() {
  return (
    <div className="rounded-lg bg-surface-container-low px-space-sm py-space-sm font-label-sm text-label-sm text-on-surface-variant">
      <p className="text-on-surface">
        Người nhận làm được gì phụ thuộc cả <b>vai trò</b> lẫn <b>quyền</b> bạn
        chọn ở đây:
      </p>
      <ul className="mt-1 list-disc space-y-0.5 pl-4">
        <li>
          <b>Chỉ xem</b>: xem hồ sơ, kết quả và trích dẫn.
        </li>
        <li>
          <b>Được sửa</b>: Vận hành sửa hồ sơ và chạy lại; Thẩm định rà soát
          trích dẫn, xung đột.
        </li>
        <li>
          Chỉ Quản trị duyệt hồ sơ. Chỉ chủ hồ sơ hoặc Quản trị đổi được quyền.
        </li>
      </ul>
    </div>
  )
}

function pendingInvite(
  dossier: Dossier,
  userId: string | undefined,
  email: string | undefined,
) {
  const normalized = email?.trim().toLowerCase()
  return dossier.shares?.some(
    (item) =>
      item.status === 'invited' &&
      ((userId && item.id === userId) ||
        (normalized && item.email.trim().toLowerCase() === normalized)),
  )
}
