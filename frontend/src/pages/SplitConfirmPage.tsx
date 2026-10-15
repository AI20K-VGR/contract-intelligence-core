import { useEffect, useMemo, useState } from 'react'
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom'
import {
  MAX_DOSSIER_DOCUMENTS,
  splitDossier,
  splitErrorMessage,
  type SplitResult,
} from '../api/dossiers'
import { getDossierStructure, type DossierStructure } from '../api/structure'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { useDossierPermissions } from '../auth/dossierPermissions'
import { MaterialIcon } from '../components/icons'
import { SplitPageStrip } from '../components/SplitPageStrip'
import { progressPath } from '../data/dossiers'
import {
  useHeaderShowsPageTitle,
  usePageBreadcrumb,
  usePageTitle,
} from '../hooks/usePageTitle'
import {
  addPart,
  initialParts,
  removePart,
  splitAtPage,
  resolveParts,
  toRequestParts,
  validateParts,
  type DraftPart,
  type SplitRole,
} from '../split/parts'

const roleLabels: Record<SplitRole, string> = {
  contract: 'Hợp đồng chính',
  annex: 'Phụ lục',
}

export function SplitConfirmPage() {
  const { dossierId = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const backTo = user ? dossiersPath(user.role) : '/ho-so'
  const backLabel = user ? dossiersLabel(user.role, user.backendRole) : 'Hồ sơ'
  const permissions = useDossierPermissions(dossierId)
  const canEdit = permissions.canEdit

  const [dossier, setDossier] = useState<DossierStructure | null>(null)
  const [parts, setParts] = useState<DraftPart[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState<SplitResult | null>(null)
  const [warn, setWarn] = useState(false)

  usePageTitle(dossier?.name ?? 'Xác nhận tách file')
  usePageBreadcrumb([
    { label: backLabel, to: backTo },
    { label: 'Xác nhận tách file' },
    ...(dossier?.name ? [{ label: dossier.name }] : []),
  ])
  const titleInHeader = useHeaderShowsPageTitle()

  // File cần tách là tệp hợp đồng người dùng vừa tải lên.
  const source = useMemo(
    () =>
      dossier?.documents.find((item) => item.role === 'contract') ??
      dossier?.documents[0] ??
      null,
    [dossier],
  )
  const pageCount = source?.pageCount ?? 0

  useEffect(() => {
    if (!dossierId) return
    const controller = new AbortController()
    getDossierStructure(dossierId, controller.signal)
      .then((next) => {
        if (controller.signal.aborted) return
        setDossier(next)
        const file =
          next.documents.find((item) => item.role === 'contract') ??
          next.documents[0]
        setParts(initialParts(file?.pageCount ?? 0))
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setLoadError(splitErrorMessage(cause))
      })
    return () => controller.abort()
  }, [dossierId])

  const resolved = useMemo(
    () => resolveParts(parts, pageCount),
    [parts, pageCount],
  )
  const problem = useMemo(
    () => (parts.length ? validateParts(parts, pageCount) : null),
    [parts, pageCount],
  )
  const lastPart = resolved[resolved.length - 1]
  // Tệp gốc được thay bằng các phần; các tài liệu còn lại của hồ sơ vẫn tính vào trần.
  const otherDocuments = Math.max(0, (dossier?.documents.length ?? 1) - 1)
  const canAdd =
    Boolean(lastPart && lastPart.pageEnd > lastPart.pageStart) &&
    parts.length + otherDocuments < MAX_DOSSIER_DOCUMENTS

  function updatePart(key: string, patch: Partial<DraftPart>) {
    setParts((current) =>
      current.map((part) => (part.key === key ? { ...part, ...patch } : part)),
    )
  }

  // Đổi các phần thì cảnh báo cũ không còn đúng, hỏi lại từ đầu.
  useEffect(() => {
    setWarn(false)
  }, [parts])

  function askConfirm() {
    if (problem || saving) return
    // Một phần phủ cả file: không tách, file gốc được giữ nguyên.
    if (parts.length <= 1) {
      void confirm()
      return
    }
    setWarn(true)
  }

  async function confirm() {
    if (!source || saving || problem) return
    setSaving(true)
    setSaveError(null)
    try {
      const result = await splitDossier(
        dossierId,
        source.id,
        toRequestParts(parts, pageCount),
      )
      setDone(result)
      window.setTimeout(() => {
        navigate(progressPath(dossierId), {
          state: location.state ?? { name: dossier?.name },
        })
      }, 1500)
    } catch (cause: unknown) {
      setSaveError(splitErrorMessage(cause))
    } finally {
      setSaving(false)
    }
  }

  if (!user) return null
  if (!canEdit) {
    return <Navigate to={backTo} replace />
  }
  // Hồ sơ không chờ tách (đã tách hoặc không phải file trộn): sang tiến trình.
  if (dossier && dossier.metadata?.split_pending !== true && !done) {
    return <Navigate to={progressPath(dossierId)} replace />
  }

  return (
    <div className="flex w-full flex-col gap-space-lg pb-margin-lg">
      {/* Header đã hiện Hồ sơ › Xác nhận tách file › tên hồ sơ. */}
      {titleInHeader ? null : (
        <h1 className="pt-space-md font-headline-lg text-headline-lg text-primary">
          Xác nhận tách file
        </h1>
      )}

      {loadError ? (
        <div className="rounded-lg bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container">
          {loadError}
        </div>
      ) : null}

      {!dossier && !loadError ? (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Đang tải hồ sơ…
        </p>
      ) : null}

      {dossier && source ? (
        // Tách xong thì giữ trang, khóa thao tác trong lúc chờ chuyển sang OCR.
        <div
          aria-disabled={done ? true : undefined}
          className={`flex flex-col gap-space-lg ${done ? 'pointer-events-none opacity-60' : ''}`}
        >
          <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
            <div className="flex items-center gap-space-md">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-700">
                <MaterialIcon name="picture_as_pdf" className="text-[24px]" />
              </span>
              <div className="min-w-0">
                <p className="truncate font-title-sm text-title-sm font-semibold text-on-surface">
                  {source.filename}
                </p>
                <p className="font-code-sm text-code-sm text-on-surface-variant">
                  {pageCount > 0 ? `${pageCount} trang` : 'Chưa biết số trang'}
                </p>
              </div>
            </div>

            <SplitPageStrip
              disabled={saving}
              documentId={source.id}
              pageCount={pageCount}
              parts={resolved}
              onStartAnnex={(page) => setParts(splitAtPage(page, pageCount))}
            />
          </section>

          <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
            <div className="flex items-center justify-between gap-space-sm">
              <div className="flex flex-col">
                <h2 className="font-title-sm text-title-sm font-semibold text-on-surface">
                  Các phần sau khi tách
                </h2>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  {parts.length > 1
                    ? `File sẽ thành ${parts.length} tài liệu riêng.`
                    : 'Giữ nguyên một tài liệu.'}
                </p>
              </div>
              <button
                className="inline-flex h-9 items-center gap-1 rounded-lg border border-brand-300 bg-brand-50 px-space-sm font-body-sm text-body-sm font-semibold text-brand-800 hover:bg-brand-100 disabled:opacity-50"
                disabled={saving || !canAdd}
                type="button"
                onClick={() =>
                  setParts((current) => addPart(current, pageCount))
                }
              >
                <MaterialIcon name="add" className="text-[16px]" />
                Thêm phần
              </button>
            </div>

            <ol className="flex flex-col gap-space-sm">
              {resolved.map((part, index) => {
                const last = index === resolved.length - 1
                const draft = parts[index]
                const annex = part.role === 'annex'
                const valid = part.pageEnd >= part.pageStart
                const count = valid ? part.pageEnd - part.pageStart + 1 : 0
                const total = Math.max(pageCount, 1)
                return (
                  <li
                    key={part.key}
                    className="grid grid-cols-[auto_1fr_auto] items-center gap-x-space-md gap-y-space-sm rounded-lg bg-surface-container-low px-space-md py-space-sm md:grid-cols-[auto_13rem_11rem_1fr_auto]"
                  >
                    <span
                      className={`flex h-8 w-8 items-center justify-center rounded-full font-label-md text-label-md font-bold ${
                        annex
                          ? 'bg-brand-300 text-brand-900'
                          : 'bg-brand-700 text-white'
                      }`}
                    >
                      {index + 1}
                    </span>
                    <select
                      aria-label={`Vai trò của phần ${index + 1}`}
                      className="h-9 w-full rounded-md bg-surface-container-lowest px-2 font-body-sm text-body-sm font-semibold text-on-surface ring-1 ring-surface-container-high"
                      disabled={saving}
                      value={part.role}
                      onChange={(event) =>
                        updatePart(part.key, {
                          role: event.target.value as SplitRole,
                        })
                      }
                    >
                      <option value="contract">{roleLabels.contract}</option>
                      <option value="annex">{roleLabels.annex}</option>
                    </select>
                    <div className="col-start-2 row-start-2 flex items-center gap-1.5 font-body-sm text-body-sm text-on-surface-variant md:col-start-auto md:row-start-auto">
                      Trang
                      <span className="font-code-sm text-code-sm font-semibold text-on-surface">
                        {part.pageStart}
                      </span>
                      –
                      {last ? (
                        <span className="font-code-sm text-code-sm font-semibold text-on-surface">
                          {pageCount}
                        </span>
                      ) : (
                        <input
                          aria-label={`Trang cuối của phần ${index + 1}`}
                          className="h-8 w-14 rounded-md bg-surface-container-lowest px-1 text-center font-code-sm text-code-sm font-semibold text-on-surface ring-1 ring-surface-container-high"
                          disabled={saving}
                          max={pageCount}
                          min={part.pageStart}
                          type="number"
                          value={draft?.end ?? part.pageEnd}
                          onChange={(event) =>
                            updatePart(part.key, {
                              end: Number.parseInt(event.target.value, 10) || 0,
                            })
                          }
                        />
                      )}
                    </div>
                    {/* Vị trí của phần trong cả file. */}
                    <div className="col-span-3 flex items-center gap-space-sm md:col-span-1">
                      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-surface-container-high">
                        {valid ? (
                          <span
                            className={`absolute inset-y-0 rounded-full ${annex ? 'bg-brand-300' : 'bg-brand-700'}`}
                            style={{
                              left: `${((part.pageStart - 1) / total) * 100}%`,
                              width: `${(count / total) * 100}%`,
                            }}
                          />
                        ) : null}
                      </div>
                      <span
                        className={`w-16 shrink-0 text-right font-code-sm text-code-sm ${valid ? 'text-on-surface-variant' : 'text-error'}`}
                      >
                        {valid ? `${count} trang` : 'Sai trang'}
                      </span>
                    </div>
                    <div className="col-start-3 row-start-1 flex w-9 justify-end md:col-start-auto md:row-start-auto">
                      {parts.length > 1 ? (
                        <button
                          aria-label={`Xóa phần ${index + 1}`}
                          className="flex h-9 w-9 items-center justify-center rounded-md text-secondary hover:bg-surface-container hover:text-error disabled:opacity-50"
                          disabled={saving}
                          title="Xóa phần này"
                          type="button"
                          onClick={() =>
                            setParts((current) => removePart(current, part.key))
                          }
                        >
                          <MaterialIcon name="delete" className="text-[18px]" />
                        </button>
                      ) : null}
                    </div>
                  </li>
                )
              })}
            </ol>

            {problem ? (
              <p className="font-body-sm text-body-sm text-error">{problem}</p>
            ) : null}
            {saveError ? (
              <p className="rounded-lg bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container">
                {saveError}
              </p>
            ) : null}

            {warn ? (
              <div
                className="rounded-lg border border-amber-400 bg-amber-50 px-space-md py-space-sm font-body-sm text-body-sm text-on-surface"
                role="alert"
              >
                <p className="flex items-center gap-1 font-semibold text-amber-900">
                  <MaterialIcon name="warning" className="text-[18px]" />
                  Tách xong không sửa lại được
                </p>
                <p className="mt-1">
                  File gốc sẽ bị bỏ và thay bằng {parts.length} tài liệu riêng.
                  Nếu tách sai, bạn phải xóa hồ sơ rồi tải lên lại.
                </p>
              </div>
            ) : null}

            <div className="flex flex-col-reverse gap-space-sm border-t border-surface-container pt-space-md sm:flex-row sm:items-center sm:justify-end">
              <button
                className="inline-flex h-11 items-center justify-center gap-1.5 rounded-lg bg-primary px-space-lg font-label-md text-label-md font-semibold text-on-primary disabled:opacity-50 sm:order-last"
                disabled={saving || problem !== null}
                type="button"
                onClick={() => (warn ? void confirm() : askConfirm())}
              >
                <MaterialIcon name="check" className="text-[18px]" />
                {saving
                  ? 'Đang tách…'
                  : warn
                    ? 'Vẫn tách'
                    : parts.length > 1
                      ? `Xác nhận tách thành ${parts.length} tài liệu`
                      : 'Xác nhận, không cần tách'}
              </button>
              {warn ? (
                <button
                  className="h-11 rounded-lg px-space-lg font-body-sm text-body-sm text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface disabled:opacity-50"
                  disabled={saving}
                  type="button"
                  onClick={() => setWarn(false)}
                >
                  Quay lại chỉnh
                </button>
              ) : (
                <Link
                  className="flex h-11 items-center justify-center rounded-lg px-space-lg font-body-sm text-body-sm text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface"
                  to={backTo}
                >
                  Để sau
                </Link>
              )}
            </div>
          </section>
        </div>
      ) : null}

      {done ? (
        <div
          className="fixed top-20 right-6 z-[70] flex w-[min(24rem,calc(100vw-3rem))] items-start gap-space-md rounded-lg border border-surface-container bg-surface-container-lowest px-space-lg py-space-md font-body-sm text-body-sm text-on-surface shadow-md"
          role="status"
        >
          <MaterialIcon
            name="check_circle"
            className="shrink-0 text-[20px] text-emerald-600"
          />
          <div className="flex min-w-0 flex-col gap-1">
            <p className="font-semibold">
              Đã tách thành {done.documents.length} tài liệu
            </p>
            <ul className="flex flex-col text-on-surface-variant">
              {done.documents.map((item) => (
                <li key={item.id}>
                  {roleLabels[item.role as SplitRole] ?? item.role} · trang{' '}
                  {item.page_start}–{item.page_end}
                </li>
              ))}
            </ul>
            <p className="text-on-surface-variant">
              Đang chuyển sang tiến trình OCR…
            </p>
          </div>
        </div>
      ) : null}
    </div>
  )
}
