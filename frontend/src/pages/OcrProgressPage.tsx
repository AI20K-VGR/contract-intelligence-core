import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  loadContractOcrPages,
  restartDossierOcr,
  restartOcrErrorMessage,
  type OcrPageRow,
  type OcrState,
} from '../api/dossiers'
import { getDossierStructure } from '../api/structure'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

const kindLabels: Record<string, string> = {
  scanned: 'Bản scan',
  native: 'Có lớp chữ',
  hybrid: 'Trộn scan và chữ',
}

function pageFailed(page: OcrPageRow) {
  return page.status === 'FAILED' || Boolean(page.error)
}

function pageDone(page: OcrPageRow) {
  return page.status === 'SUCCESS' || page.status === 'PARTIAL'
}

function describeActivity(jobStatus: string | null, pages: OcrPageRow[]) {
  if (pages.length === 0) {
    if (jobStatus === 'processing') {
      return 'Đang gửi tệp sang bộ nhận diện chữ. Chưa có trang nào trả kết quả.'
    }
    return 'Chưa chạy OCR. Bấm Tiếp tục OCR để bắt đầu.'
  }
  const failed = pages.filter(pageFailed)
  const done = pages.filter(pageDone)
  if (failed.length === pages.length) {
    return `OCR dừng ở bước nhận diện chữ, trên cả ${pages.length} trang.`
  }
  if (failed.length > 0) {
    const numbers = failed.map((page) => page.pageNo).join(', ')
    return `OCR lỗi ở trang ${numbers}. Các trang còn lại ${done.length > 0 ? 'đã có chữ' : 'chưa xong'}.`
  }
  if (jobStatus === 'processing') {
    return `Đang nhận diện chữ. ${done.length}/${pages.length} trang đã xong.`
  }
  return `Đã nhận diện xong ${pages.length} trang.`
}

function overallState(
  jobStatus: string | null,
  pages: OcrPageRow[],
): OcrState {
  if (pages.some(pageFailed)) return 'error'
  if (pages.length === 0) {
    return jobStatus === 'processing' ? 'running' : 'pending'
  }
  if (jobStatus === 'processing' || jobStatus === 'uploaded') return 'running'
  return 'done'
}

export function OcrProgressPage() {
  const { dossierId = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const backTo = user ? dossiersPath(user.role) : '/ho-so'
  const backLabel = user ? dossiersLabel(user.role) : 'Hồ sơ'
  const [name, setName] = useState('Tiến trình OCR')
  const [filename, setFilename] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<string | null>(null)
  const [pages, setPages] = useState<OcrPageRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [watching, setWatching] = useState(false)

  usePageTitle(name)
  const titleInHeader = useHeaderShowsPageTitle()

  useEffect(() => {
    const restart = Boolean(
      (location.state as { restart?: boolean } | null)?.restart,
    )
    if (!restart || !dossierId) return
    navigate(location.pathname, { replace: true, state: null })
    setWatching(true)
    setBusy(true)
    setActionError(null)
    void restartDossierOcr(dossierId)
      .then(() => {
        setJobStatus('processing')
        setReloadKey((value) => value + 1)
      })
      .catch((cause: unknown) => {
        setActionError(restartOcrErrorMessage(cause))
        setWatching(false)
      })
      .finally(() => {
        setBusy(false)
      })
  }, [dossierId, location.pathname, location.state, navigate])

  useEffect(() => {
    if (!dossierId) return
    const controller = new AbortController()
    let timer: number | undefined
    let stopped = false

    async function load() {
      try {
        const [detail, ocr] = await Promise.all([
          getDossierStructure(dossierId, controller.signal),
          loadContractOcrPages(dossierId, controller.signal),
        ])
        if (stopped) return
        setName(detail.name)
        setJobStatus(detail.latestJobStatus)
        setFilename(ocr.filename)
        setPages(ocr.pages)
        setError(null)
        const state = overallState(detail.latestJobStatus, ocr.pages)
        if (state === 'done') setWatching(false)
        if (state === 'running' || watching) {
          timer = window.setTimeout(() => {
            void load()
          }, 4000)
        }
      } catch (cause) {
        if (controller.signal.aborted || stopped) return
        setError(
          cause instanceof Error ? cause.message : 'Không tải được tiến trình OCR.',
        )
      }
    }

    void load()
    return () => {
      stopped = true
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [dossierId, reloadKey, watching])

  useEffect(() => {
    if (!watching) return
    const timer = window.setTimeout(() => setWatching(false), 120000)
    return () => window.clearTimeout(timer)
  }, [watching])

  const state = overallState(jobStatus, pages)
  const activity =
    watching && state !== 'done'
      ? 'Đang chạy lại OCR. Kết quả từng trang bên dưới còn là lần trước, cho đến khi lần mới ghi xong.'
      : describeActivity(jobStatus, pages)
  const failedPages = pages.filter(pageFailed)

  async function retry() {
    if (!dossierId) return
    setBusy(true)
    setActionError(null)
    try {
      await restartDossierOcr(dossierId)
      setJobStatus('processing')
      setReloadKey((value) => value + 1)
    } catch (cause) {
      setActionError(restartOcrErrorMessage(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <div className="flex flex-col gap-space-sm pt-space-lg pb-space-lg">
        <nav className="flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
          <Link className="hover:text-primary transition-colors" to={backTo}>
            {backLabel}
          </Link>
          <MaterialIcon name="chevron_right" className="text-[14px]" />
          <span className="text-on-surface font-semibold">Tiến trình OCR</span>
        </nav>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-md">
          <div className="flex flex-col gap-space-xs max-w-3xl">
            {titleInHeader ? null : (
              <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
                {name}
              </h1>
            )}
            <p className="font-body-md text-body-md text-on-surface-variant">
              {filename ?? 'Chưa có tệp hợp đồng.'}
            </p>
          </div>
          {state === 'pending' || state === 'error' ? (
            <button
              className="h-10 px-space-lg bg-primary text-on-primary rounded-lg font-body-sm text-body-sm font-semibold self-start"
              disabled={busy}
              type="button"
              onClick={() => {
                void retry()
              }}
            >
              {busy
                ? 'Đang gửi…'
                : state === 'pending'
                  ? 'Tiếp tục OCR'
                  : 'OCR lại'}
            </button>
          ) : null}
        </div>
      </div>

      {error ? (
        <p className="font-body-sm text-body-sm text-error" role="alert">
          {error}
        </p>
      ) : (
        <div className="flex flex-col gap-space-md">
          <section className="rounded-lg bg-surface-container-lowest p-space-lg shadow-[0_1px_3px_rgba(15,23,42,0.06)]">
            <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
              Đang làm gì
            </p>
            <p className="mt-space-sm font-title-sm text-title-sm text-on-surface">
              {activity}
            </p>
            {actionError ? (
              <p className="mt-space-sm font-body-sm text-body-sm text-error" role="alert">
                {actionError}
              </p>
            ) : null}
            <ol className="mt-space-lg flex flex-col gap-space-sm">
              <Step
                detail={filename ? 'Đã có tệp' : 'Chưa có tệp'}
                status={filename ? 'done' : 'waiting'}
                title="1. Tải tệp"
              />
              <Step
                detail={
                  failedPages.length > 0
                    ? `${failedPages.length} trang lỗi`
                    : state === 'running'
                      ? 'Đang nhận diện'
                      : state === 'done'
                        ? 'Xong'
                        : 'Chưa chạy'
                }
                status={
                  watching && state !== 'done'
                    ? 'active'
                    : failedPages.length > 0
                      ? 'error'
                      : state === 'running'
                        ? 'active'
                        : state === 'done'
                          ? 'done'
                          : 'waiting'
                }
                title="2. Nhận diện chữ"
              />
              <Step
                detail={state === 'done' ? 'Đã ghi dòng OCR' : 'Chờ nhận diện xong'}
                status={state === 'done' ? 'done' : 'waiting'}
                title="3. Ghi kết quả"
              />
            </ol>
          </section>

          <section className="rounded-lg bg-surface-container-lowest shadow-[0_1px_3px_rgba(15,23,42,0.06)] overflow-hidden">
            <div className="px-space-lg py-space-md border-b border-surface-container">
              <h2 className="font-title-sm text-title-sm text-on-surface">
                Từng trang
              </h2>
            </div>
            {pages.length === 0 ? (
              <p className="px-space-lg py-space-lg font-body-sm text-body-sm text-on-surface-variant">
                Chưa có trang nào. OCR chưa trả kết quả.
              </p>
            ) : (
              <ul className="divide-y divide-surface-container-low">
                {pages.map((page) => (
                  <li
                    key={`${page.pageNo}-${page.status}`}
                    className="px-space-lg py-space-md flex flex-col gap-1"
                  >
                    <div className="flex items-center gap-space-sm">
                      <span className="font-title-sm text-title-sm text-on-surface">
                        Trang {page.pageNo > 0 ? page.pageNo : '—'}
                      </span>
                      <span className="font-label-sm text-label-sm text-on-surface-variant">
                        {kindLabels[page.kind] ?? (page.kind || 'Chưa rõ loại')}
                      </span>
                      <PageBadge page={page} />
                    </div>
                    {page.error ? (
                      <p className="font-body-sm text-body-sm text-error">
                        {page.error}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  )
}

function Step({
  title,
  detail,
  status,
}: {
  title: string
  detail: string
  status: 'done' | 'active' | 'waiting' | 'error'
}) {
  const tone =
    status === 'done'
      ? 'bg-emerald-100 text-emerald-900'
      : status === 'active'
        ? 'bg-amber-100 text-amber-950'
        : status === 'error'
          ? 'bg-error-container text-on-error-container'
          : 'bg-surface-container text-on-surface-variant'
  return (
    <li className="flex items-center justify-between gap-space-md">
      <span className="font-body-sm text-body-sm text-on-surface">{title}</span>
      <span
        className={`px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold ${tone}`}
      >
        {detail}
      </span>
    </li>
  )
}

function PageBadge({ page }: { page: OcrPageRow }) {
  if (pageFailed(page)) {
    return (
      <span className="px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-error-container text-on-error-container">
        Lỗi
      </span>
    )
  }
  if (pageDone(page)) {
    return (
      <span className="px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-emerald-100 text-emerald-900">
        Xong
      </span>
    )
  }
  return (
    <span className="px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-amber-100 text-amber-950">
      Đang chờ
    </span>
  )
}
