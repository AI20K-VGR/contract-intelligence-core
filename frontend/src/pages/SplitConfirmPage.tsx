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
import { MaterialIcon } from '../components/icons'
import { SplitPageStrip } from '../components/SplitPageStrip'
import { progressPath } from '../data/dossiers'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'
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
  const backLabel = user ? dossiersLabel(user.role) : 'Hồ sơ'
  const canEdit =
    user?.backendRole === 'OPERATOR' || user?.backendRole === 'ADMINISTRATOR'

  const [dossier, setDossier] = useState<DossierStructure | null>(null)
  const [parts, setParts] = useState<DraftPart[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState<SplitResult | null>(null)
  const [warn, setWarn] = useState(false)

  usePageTitle(dossier?.name ?? 'Xác nhận tách file')
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
      <div className="flex flex-col gap-space-sm pt-space-md">
        <nav className="flex items-center gap-space-xs font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
          <Link className="hover:text-primary" to={backTo}>
            {backLabel}
          </Link>
          <MaterialIcon name="chevron_right" className="text-[14px]" />
          <span className="font-semibold text-on-surface">
            Xác nhận tách file
          </span>
        </nav>
        {titleInHeader ? null : (
          <h1 className="font-headline-lg text-headline-lg text-primary">
            Xác nhận tách file
          </h1>
        )}
        <p className="max-w-3xl font-body-md text-body-md text-on-surface-variant">
          File này gồm cả hợp đồng và phụ lục. Chọn trang đầu tiên của phụ lục
          để chia file. Mỗi phần sẽ thành một tài liệu riêng rồi mới OCR.
        </p>
      </div>

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

      {dossier && source && !done ? (
        <div className="grid grid-cols-1 items-start gap-space-lg xl:grid-cols-12">
          <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-lowest p-space-lg shadow-sm xl:col-span-8">
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

            <div className="flex flex-wrap items-center gap-x-space-lg gap-y-1 rounded-lg bg-surface-container-low px-space-md py-space-sm font-body-sm text-body-sm text-on-surface-variant">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-sm bg-amber-400" />
                Hợp đồng
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-sm bg-sky-500" />
                Phụ lục
              </span>
              <span>
                Bấm <strong className="text-on-surface">Phụ lục từ đây</strong>{' '}
                ở trang đầu tiên của phụ lục.
              </span>
            </div>

            <SplitPageStrip
              disabled={saving}
              documentId={source.id}
              pageCount={pageCount}
              parts={resolved}
              onStartAnnex={(page) => setParts(splitAtPage(page, pageCount))}
            />
          </section>

          <aside className="flex flex-col gap-space-md rounded-xl bg-surface-container-lowest p-space-lg shadow-sm xl:sticky xl:top-space-md xl:col-span-4">
            <div className="flex items-center justify-between gap-space-sm">
              <h2 className="font-title-sm text-title-sm font-semibold text-on-surface">
                Các phần sau khi tách
              </h2>
              <button
                className="inline-flex h-8 items-center gap-1 rounded-md bg-surface-container-low px-space-sm font-body-sm text-body-sm text-on-surface hover:bg-surface-container disabled:opacity-50"
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
                return (
                  <li
                    key={part.key}
                    className={`flex flex-col gap-space-sm rounded-lg border-l-4 bg-surface-container-low px-space-md py-space-sm ${
                      annex ? 'border-sky-500' : 'border-amber-400'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-space-sm">
                      <span className="font-label-md text-label-md font-semibold text-on-surface">
                        Phần {index + 1}
                      </span>
                      <span className="font-code-sm text-code-sm text-on-surface-variant">
                        {part.pageEnd >= part.pageStart
                          ? `Trang ${part.pageStart}–${part.pageEnd} · ${part.pageEnd - part.pageStart + 1} trang`
                          : 'Chưa hợp lệ'}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-space-sm">
                      <select
                        aria-label={`Vai trò của phần ${index + 1}`}
                        className="h-9 min-w-0 flex-1 rounded-md bg-surface-container-lowest px-2 font-body-sm text-body-sm text-on-surface ring-1 ring-surface-container-high"
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
                      <label className="inline-flex items-center gap-1.5 font-body-sm text-body-sm text-on-surface-variant">
                        đến trang
                        <input
                          aria-label={`Trang cuối của phần ${index + 1}`}
                          className="h-9 w-16 rounded-md bg-surface-container-lowest px-2 text-center font-code-sm text-code-sm text-on-surface ring-1 ring-surface-container-high disabled:bg-surface-container disabled:text-on-surface-variant"
                          disabled={last || saving}
                          max={pageCount}
                          min={part.pageStart}
                          type="number"
                          value={
                            last ? pageCount : (draft?.end ?? part.pageEnd)
                          }
                          onChange={(event) =>
                            updatePart(part.key, {
                              end: Number.parseInt(event.target.value, 10) || 0,
                            })
                          }
                        />
                      </label>
                      {parts.length > 1 ? (
                        <button
                          aria-label={`Xóa phần ${index + 1}`}
                          className="flex h-9 w-9 items-center justify-center rounded-md text-secondary hover:bg-surface-container hover:text-error disabled:opacity-50"
                          disabled={saving}
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

            <div className="flex flex-col gap-space-sm border-t border-surface-container pt-space-md">
              <button
                className="inline-flex h-11 items-center justify-center gap-1.5 rounded-lg bg-primary px-space-lg font-label-md text-label-md font-semibold text-on-primary disabled:opacity-50"
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
                  className="h-9 rounded-lg font-body-sm text-body-sm text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface disabled:opacity-50"
                  disabled={saving}
                  type="button"
                  onClick={() => setWarn(false)}
                >
                  Quay lại chỉnh
                </button>
              ) : (
                <Link
                  className="flex h-9 items-center justify-center rounded-lg font-body-sm text-body-sm text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface"
                  to={backTo}
                >
                  Để sau
                </Link>
              )}
            </div>
          </aside>
        </div>
      ) : null}

      {done ? (
        <section className="rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
          <p className="flex items-center gap-1.5 font-title-sm text-title-sm font-semibold text-on-surface">
            <MaterialIcon
              name="check_circle"
              className="text-[22px] text-emerald-600"
            />
            Đã tách thành {done.documents.length} tài liệu
          </p>
          <ul className="mt-space-sm flex flex-col gap-1">
            {done.documents.map((item) => (
              <li
                key={item.id}
                className="font-body-sm text-body-sm text-on-surface"
              >
                {roleLabels[item.role as SplitRole] ?? item.role} · trang{' '}
                {item.page_start}–{item.page_end} ({item.page_count} trang)
              </li>
            ))}
          </ul>
          <p className="mt-space-sm font-body-sm text-body-sm text-on-surface-variant">
            Đang chuyển sang tiến trình OCR…
          </p>
        </section>
      ) : null}
    </div>
  )
}
