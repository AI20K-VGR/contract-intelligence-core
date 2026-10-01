import { useEffect, useMemo, useState } from 'react'
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom'
import {
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
  const canAdd = Boolean(lastPart && lastPart.pageEnd > lastPart.pageStart)

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
    <div className="flex w-full flex-col pb-margin-lg">
      <nav className="flex items-center gap-space-xs pt-space-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
        <Link className="hover:text-primary" to={backTo}>
          {backLabel}
        </Link>
        <MaterialIcon name="chevron_right" className="text-[14px]" />
        <span className="font-semibold text-on-surface">
          Xác nhận tách file
        </span>
      </nav>
      {titleInHeader ? null : (
        <h1 className="mt-space-sm font-headline-lg text-headline-lg text-primary">
          Xác nhận tách file
        </h1>
      )}
      <p className="mt-space-sm max-w-3xl font-body-md text-body-md text-on-surface-variant">
        File này gồm cả hợp đồng và phụ lục. Chia file thành từng phần theo
        khoảng trang rồi xác nhận. Mỗi phần sẽ là một tài liệu riêng, sau đó mới
        OCR.
      </p>

      {loadError ? (
        <div className="mt-space-lg rounded bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container">
          {loadError}
        </div>
      ) : null}

      {!dossier && !loadError ? (
        <p className="mt-space-lg font-body-sm text-body-sm text-on-surface-variant">
          Đang tải hồ sơ…
        </p>
      ) : null}

      {dossier && source && !done ? (
        <section className="mt-space-lg rounded-lg bg-surface-container-lowest p-space-lg shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-space-sm">
            <div className="flex min-w-0 items-center gap-space-sm">
              <MaterialIcon
                name="picture_as_pdf"
                className="text-[22px] text-red-700"
              />
              <div className="min-w-0">
                <p className="truncate font-title-sm text-title-sm font-semibold text-on-surface">
                  {source.filename}
                </p>
                <p className="font-code-sm text-code-sm text-on-surface-variant">
                  {pageCount > 0 ? `${pageCount} trang` : 'Chưa biết số trang'}
                </p>
              </div>
            </div>
            <button
              className="inline-flex h-9 items-center gap-1 rounded bg-surface-container-low px-space-sm font-body-sm text-body-sm text-on-surface hover:bg-surface-container disabled:opacity-50"
              disabled={saving || !canAdd}
              type="button"
              onClick={() => setParts((current) => addPart(current, pageCount))}
            >
              <MaterialIcon name="add" className="text-[18px]" />
              Thêm phần
            </button>
          </div>

          <div className="mt-space-md">
            <p className="mb-space-xs font-label-sm text-label-sm text-on-surface-variant">
              Xem từng trang rồi bấm &quot;Phụ lục từ đây&quot; ở trang đầu tiên
              của phụ lục. Viền vàng là hợp đồng, viền xanh là phụ lục.
            </p>
            <SplitPageStrip
              disabled={saving}
              documentId={source.id}
              pageCount={pageCount}
              parts={resolved}
              onStartAnnex={(page) => setParts(splitAtPage(page, pageCount))}
            />
          </div>

          <ol className="mt-space-md flex flex-col gap-space-sm">
            {resolved.map((part, index) => {
              const last = index === resolved.length - 1
              const draft = parts[index]
              return (
                <li
                  key={part.key}
                  className="flex flex-wrap items-center gap-space-sm rounded-lg bg-surface-container-low px-space-md py-space-sm"
                >
                  <span className="font-label-md text-label-md font-semibold text-on-surface">
                    Phần {index + 1}
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">
                    Từ trang
                  </span>
                  <span className="rounded bg-surface-container px-2 py-1 font-code-sm text-code-sm">
                    {part.pageStart}
                  </span>
                  <label className="inline-flex items-center gap-1 font-body-sm text-body-sm text-on-surface-variant">
                    đến trang
                    <input
                      aria-label={`Trang cuối của phần ${index + 1}`}
                      className="h-8 w-20 rounded bg-surface px-2 font-code-sm text-code-sm text-on-surface disabled:opacity-60"
                      disabled={last || saving}
                      max={pageCount}
                      min={part.pageStart}
                      type="number"
                      value={last ? pageCount : (draft?.end ?? part.pageEnd)}
                      onChange={(event) =>
                        updatePart(part.key, {
                          end: Number.parseInt(event.target.value, 10) || 0,
                        })
                      }
                    />
                  </label>
                  <select
                    aria-label={`Vai trò của phần ${index + 1}`}
                    className="h-8 rounded bg-surface px-2 font-body-sm text-body-sm"
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
                  <span className="font-label-sm text-label-sm text-secondary">
                    {part.pageEnd >= part.pageStart
                      ? `${part.pageEnd - part.pageStart + 1} trang`
                      : ''}
                  </span>
                  {parts.length > 1 ? (
                    <button
                      aria-label={`Xóa phần ${index + 1}`}
                      className="ml-auto text-secondary hover:text-error disabled:opacity-50"
                      disabled={saving}
                      type="button"
                      onClick={() =>
                        setParts((current) => removePart(current, part.key))
                      }
                    >
                      <MaterialIcon name="delete" className="text-[18px]" />
                    </button>
                  ) : null}
                </li>
              )
            })}
          </ol>

          {problem ? (
            <p className="mt-space-sm font-body-sm text-body-sm text-error">
              {problem}
            </p>
          ) : null}
          {saveError ? (
            <p className="mt-space-sm rounded bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container">
              {saveError}
            </p>
          ) : null}

          {warn ? (
            <div
              className="mt-space-md rounded-lg border border-amber-400 bg-amber-50 px-space-md py-space-sm font-body-sm text-body-sm text-on-surface"
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

          <div className="mt-space-md flex items-center justify-end gap-space-sm">
            {warn ? (
              <button
                className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface disabled:opacity-50"
                disabled={saving}
                type="button"
                onClick={() => setWarn(false)}
              >
                Quay lại chỉnh
              </button>
            ) : (
              <Link
                className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface"
                to={backTo}
              >
                Để sau
              </Link>
            )}
            <button
              className="inline-flex h-10 items-center gap-1 rounded bg-primary px-space-lg font-label-md text-label-md font-semibold text-on-primary disabled:opacity-50"
              disabled={saving || problem !== null}
              type="button"
              onClick={() => (warn ? void confirm() : askConfirm())}
            >
              <MaterialIcon name="check" className="text-[18px]" />
              {saving ? 'Đang tách…' : warn ? 'Vẫn tách' : 'Xác nhận tách'}
            </button>
          </div>
        </section>
      ) : null}

      {done ? (
        <section className="mt-space-lg rounded-lg bg-surface-container-lowest p-space-lg shadow-sm">
          <p className="flex items-center gap-1 font-title-sm text-title-sm font-semibold text-on-surface">
            <MaterialIcon
              name="check_circle"
              className="text-[20px] text-emerald-600"
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
