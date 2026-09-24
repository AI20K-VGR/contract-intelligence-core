import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  listDossiers,
  listDossiersErrorMessage,
  updateDossierAccess,
} from '../api/dossiers'
import { listUsers, type ManagedUser } from '../api/users'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import type { Dossier } from '../data/dossiers'
import { usePageTitle } from '../hooks/usePageTitle'
import { accessLabels, dossierFromSummary } from './MyDossiersPage'

type AccessFilter = 'all' | Dossier['access']

const filters: { id: AccessFilter; label: string; dot?: string }[] = [
  { id: 'all', label: 'Tất cả' },
  { id: 'mine', label: 'Hồ sơ của tôi', dot: 'bg-emerald-600' },
  { id: 'shared_out', label: 'Hồ sơ đã chia sẻ', dot: 'bg-amber-500' },
  { id: 'shared_in', label: 'Hồ sơ được chia sẻ', dot: 'bg-[#2563eb]' },
]

export function AccessPage() {
  const { user } = useAuth()
  usePageTitle('Quyền truy cập')
  const [params, setParams] = useSearchParams()
  const selectedId = params.get('dossier')
  const [dossiers, setDossiers] = useState<Dossier[]>([])
  const [people, setPeople] = useState<ManagedUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<AccessFilter>('all')
  const [chosen, setChosen] = useState<string[]>([])
  const [savingId, setSavingId] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

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
          result.items.map((item) => dossierFromSummary(item, user?.id)),
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
  }, [user?.id])

  useEffect(() => {
    setChosen(selected?.shares?.map((item) => item.id) ?? [])
    setSaveError(null)
  }, [selected])

  function select(id: string) {
    setParams({ dossier: id })
  }

  async function saveAccess(
    dossier: Dossier,
    nextScope: Dossier['access'],
    shareIds: string[],
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
    } catch {
      setSaveError('Chưa lưu được quyền truy cập.')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <p className="font-body-sm text-body-sm text-on-surface-variant pb-space-lg">
        Phân loại hồ sơ bạn tải lên, hồ sơ bạn đã chia sẻ và hồ sơ người khác
        chia sẻ cho bạn.
      </p>

      <div className="bg-surface-container-lowest rounded-lg shadow-[0_1px_3px_rgba(15,23,42,0.06)] flex flex-col">
        <div className="p-space-md bg-surface-container-lowest">
          <div className="inline-flex items-center bg-surface-container-low p-1 rounded-lg gap-1 flex-wrap">
            {filters.map((item) => {
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
          <table className="w-full text-left font-body-sm text-body-sm border-collapse">
            <thead>
              <tr className="bg-surface-container-low text-on-secondary-container font-label-sm text-label-sm uppercase tracking-wider">
                <th className="py-3 px-space-md font-semibold">Tên hồ sơ</th>
                <th className="py-3 px-space-md font-semibold">Quyền truy cập</th>
                <th className="py-3 px-space-md font-semibold">Đổi quyền</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-low text-on-surface">
              {error ? (
                <tr>
                  <td className="py-10 px-space-md text-error" colSpan={3}>
                    {error}
                  </td>
                </tr>
              ) : null}
              {loading && dossiers.length === 0 ? (
                <tr>
                  <td
                    className="py-10 px-space-md text-on-surface-variant"
                    colSpan={3}
                  >
                    Đang tải danh sách hồ sơ…
                  </td>
                </tr>
              ) : null}
              {!loading && !error && visible.length === 0 ? (
                <tr>
                  <td
                    className="py-10 px-space-md text-on-surface-variant"
                    colSpan={3}
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
                    <td className="py-3.5 px-space-md">
                      <span className="font-title-sm text-title-sm font-semibold">
                        {item.title}
                      </span>
                      <span className="block font-code-sm text-label-sm text-on-surface-variant mt-1">
                        {item.code}
                      </span>
                    </td>
                    <td className="py-3.5 px-space-md whitespace-nowrap">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container font-label-sm text-label-sm">
                        <MaterialIcon
                          name={item.access === 'mine' ? 'lock' : 'share'}
                          className="text-[14px]"
                        />
                        {accessLabels[item.access]}
                      </span>
                    </td>
                    <td className="py-3.5 px-space-md">
                      {item.access === 'shared_in' ? (
                        <span className="font-body-sm text-body-sm text-on-surface-variant">
                          Người khác chia sẻ
                        </span>
                      ) : item.access === 'shared_out' ? (
                        <button
                          className="h-9 px-space-sm rounded bg-surface-container-low text-on-surface font-body-sm text-body-sm hover:bg-surface-container disabled:opacity-50"
                          disabled={savingId === item.id}
                          type="button"
                          onClick={() => {
                            void saveAccess(item, 'mine', [])
                          }}
                        >
                          {savingId === item.id
                            ? 'Đang lưu…'
                            : 'Đổi thành hồ sơ của tôi'}
                        </button>
                      ) : (
                        <div className="relative inline-flex items-center gap-space-sm">
                          <button
                            className={`h-9 px-space-sm rounded font-body-sm text-body-sm disabled:opacity-50 ${
                              active
                                ? 'bg-primary-container text-on-primary'
                                : 'bg-surface-container-low text-on-surface hover:bg-surface-container'
                            }`}
                            disabled={savingId === item.id}
                            type="button"
                            onClick={() =>
                              select(active ? '' : item.id)
                            }
                          >
                            Chia sẻ với người khác
                          </button>
                          {active ? (
                            <div className="absolute left-0 top-10 z-50 w-72 rounded bg-surface-container-lowest shadow-[0_8px_24px_rgba(15,23,42,0.12)] border border-surface-container p-space-sm flex flex-col gap-space-sm">
                              <div className="flex flex-col gap-1 max-h-48 overflow-auto">
                                {tenants.length === 0 ? (
                                  <p className="font-body-sm text-body-sm text-secondary px-1">
                                    Tenant chưa có người dùng khác.
                                  </p>
                                ) : (
                                  tenants.map((person) => (
                                    <label
                                      key={person.id}
                                      className="inline-flex items-center gap-2 px-1 py-1 rounded hover:bg-surface-container-low font-body-sm text-body-sm"
                                    >
                                      <input
                                        checked={chosen.includes(person.id)}
                                        type="checkbox"
                                        onChange={() =>
                                          setChosen((current) =>
                                            current.includes(person.id)
                                              ? current.filter(
                                                  (id) => id !== person.id,
                                                )
                                              : [...current, person.id],
                                          )
                                        }
                                      />
                                      <span>
                                        {person.display_name} · {person.email}
                                      </span>
                                    </label>
                                  ))
                                )}
                              </div>
                              {saveError ? (
                                <p className="font-body-sm text-body-sm text-error">
                                  {saveError}
                                </p>
                              ) : null}
                              <button
                                className="h-8 px-space-sm rounded bg-primary-container text-on-primary font-label-sm text-label-sm disabled:opacity-50"
                                disabled={
                                  savingId === item.id || chosen.length === 0
                                }
                                type="button"
                                onClick={() => {
                                  void saveAccess(item, 'shared_out', chosen)
                                }}
                              >
                                {savingId === item.id ? 'Đang lưu…' : 'Lưu quyền'}
                              </button>
                            </div>
                          ) : null}
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
