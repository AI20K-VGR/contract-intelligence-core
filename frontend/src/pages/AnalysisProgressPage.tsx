import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  deleteDossier,
  loadDocumentOcrPages,
  restartDossierOcr,
  restartOcrErrorMessage,
  type OcrPageRow,
} from '../api/dossiers'
import {
  countClauses,
  getDossierStructure,
  isOcrComplete,
  listClauses,
  structureErrorMessage,
  type DossierStructure,
  type StructureDocument,
} from '../api/structure'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { structurePath } from '../data/dossiers'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'
import { parseStructureMode, type StructureMode } from '../structure'

type FileStatus = 'done' | 'reading' | 'waiting' | 'failed'

type FileRowModel = {
  id: string
  name: string
  meta: string
  status: FileStatus
  label: string
}

type LogRowModel = {
  id: string
  text: string
  status: 'done' | 'active' | 'failed'
}

function pageDone(page: OcrPageRow) {
  return page.status === 'SUCCESS' || page.status === 'PARTIAL'
}

function pageFailed(page: OcrPageRow) {
  return page.status === 'FAILED' || Boolean(page.error)
}

function fileModel(
  document: StructureDocument,
  pages: OcrPageRow[],
  jobStatus: string | null,
  current: boolean,
): FileRowModel {
  const total = Math.max(document.pageCount, pages.length)
  const done = pages.filter(pageDone).length
  const failed = pages.filter(pageFailed).length
  const meta = total > 0 ? `• ${total} trang` : '• PDF'
  if (failed > 0 && jobStatus === 'failed') {
    return {
      id: document.id,
      name: document.filename,
      meta,
      status: 'failed',
      label: 'OCR lỗi',
    }
  }
  if (total > 0 && done >= total && isOcrComplete(jobStatus)) {
    return {
      id: document.id,
      name: document.filename,
      meta,
      status: 'done',
      label: 'Hoàn thành',
    }
  }
  if (isOcrComplete(jobStatus)) {
    return {
      id: document.id,
      name: document.filename,
      meta,
      status: 'done',
      label: 'Hoàn thành',
    }
  }
  if (
    current &&
    (jobStatus === 'processing' || jobStatus === 'uploaded' || done > 0)
  ) {
    const percent = total > 0 ? Math.round((done / total) * 100) : null
    return {
      id: document.id,
      name: document.filename,
      meta,
      status: 'reading',
      label: percent === null ? 'Đang đọc' : `Đang đọc ${percent}%`,
    }
  }
  return {
    id: document.id,
    name: document.filename,
    meta,
    status: 'waiting',
    label: 'Chờ xử lý',
  }
}

function stateStructureMode(state: unknown): StructureMode | null {
  if (!state || typeof state !== 'object') return null
  return parseStructureMode(
    (state as { structureMode?: unknown }).structureMode,
  )
}

export function AnalysisProgressPage() {
  const { dossierId = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const backTo = user ? dossiersPath(user.role) : '/ho-so'
  const backLabel = user ? dossiersLabel(user.role) : 'Hồ sơ'
  const titleInHeader = useHeaderShowsPageTitle()
  const [detail, setDetail] = useState<DossierStructure | null>(null)
  const [pagesByDoc, setPagesByDoc] = useState<Record<string, OcrPageRow[]>>({})
  const [clauseCount, setClauseCount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const passedName = (location.state as { name?: string } | null)?.name

  usePageTitle(detail?.name ?? passedName ?? 'Tiến trình phân tích')

  useEffect(() => {
    if (dossierId) return
    navigate(backTo, { replace: true })
  }, [backTo, dossierId, navigate])

  useEffect(() => {
    const restart = Boolean(
      (location.state as { restart?: boolean } | null)?.restart,
    )
    if (!restart || !dossierId) return
    navigate(location.pathname, { replace: true, state: null })
    setBusy(true)
    setError(null)
    void restartDossierOcr(dossierId)
      .then(() => setAttempt((value) => value + 1))
      .catch((cause: unknown) => setError(restartOcrErrorMessage(cause)))
      .finally(() => setBusy(false))
  }, [dossierId, location.pathname, location.state, navigate])

  useEffect(() => {
    if (!dossierId) return
    const controller = new AbortController()
    let timer: number | undefined
    let stopped = false

    async function load() {
      try {
        const next = await getDossierStructure(dossierId, controller.signal)
        if (stopped) return
        const pages = await Promise.all(
          next.documents.map(async (document) => {
            try {
              const rows = await loadDocumentOcrPages(
                document.id,
                controller.signal,
              )
              return [document.id, rows] as const
            } catch {
              return [document.id, [] as OcrPageRow[]] as const
            }
          }),
        )
        if (stopped) return
        setDetail(next)
        setPagesByDoc(Object.fromEntries(pages))
        setError(null)
        if (isOcrComplete(next.latestJobStatus)) {
          const contract =
            next.documents.find(
              (document) => document.role.toLowerCase() === 'contract',
            ) ?? next.documents[0]
          if (contract) {
            try {
              const tree = await listClauses(contract.id, controller.signal)
              if (!stopped) setClauseCount(countClauses(tree))
            } catch {
              if (!stopped) setClauseCount(null)
            }
          }
          return
        }
        if (next.latestJobStatus === 'failed') return
        setClauseCount(null)
        timer = window.setTimeout(() => {
          void load()
        }, 2000)
      } catch (cause) {
        if (controller.signal.aborted || stopped) return
        const message = structureErrorMessage(cause)
        if (!message) return
        setError(message)
      }
    }

    void load()
    return () => {
      stopped = true
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [attempt, dossierId])

  const documents = useMemo(() => detail?.documents ?? [], [detail])
  const jobStatus = detail?.latestJobStatus ?? null
  const ready = isOcrComplete(jobStatus)
  const failed = jobStatus === 'failed'
  const files = useMemo(() => {
    const current = documents.find((document) => {
      const pages = pagesByDoc[document.id] ?? []
      const total = Math.max(document.pageCount, pages.length)
      const done = pages.filter(pageDone).length
      return total === 0 || done < total
    })
    return documents.map((document) =>
      fileModel(
        document,
        pagesByDoc[document.id] ?? [],
        jobStatus,
        current?.id === document.id,
      ),
    )
  }, [documents, jobStatus, pagesByDoc])

  const pageTotals = documents.reduce(
    (totals, document) => {
      const pages = pagesByDoc[document.id] ?? []
      const total = Math.max(document.pageCount, pages.length)
      return {
        total: totals.total + total,
        done: totals.done + pages.filter(pageDone).length,
      }
    },
    { total: 0, done: 0 },
  )
  const percent =
    pageTotals.total > 0
      ? Math.round((pageTotals.done / pageTotals.total) * 100)
      : ready
        ? 100
        : 0

  const logs = useMemo(() => {
    const rows: LogRowModel[] = []
    if (documents.length > 0) {
      rows.push({
        id: 'received',
        status: 'done',
        text: `Đã tiếp nhận ${documents.length} tệp hồ sơ`,
      })
    }
    for (const file of files) {
      if (file.status === 'done') {
        rows.push({
          id: `${file.id}-done`,
          status: 'done',
          text: `Đã đọc xong ${file.name}`,
        })
      } else if (file.status === 'reading') {
        rows.push({
          id: `${file.id}-read`,
          status: 'active',
          text: `${file.label}: ${file.name}`,
        })
      } else if (file.status === 'failed') {
        rows.push({
          id: `${file.id}-fail`,
          status: 'failed',
          text: `OCR lỗi trên ${file.name}`,
        })
      }
    }
    if (ready) {
      rows.push({
        id: 'finish',
        status: 'done',
        text: 'Đã dựng xong cấu trúc. Có thể mở hồ sơ.',
      })
    }
    return rows
  }, [documents.length, files, ready])

  const mode = detail?.structureMode ?? stateStructureMode(location.state)

  async function cancelJob() {
    if (!dossierId || busy) return
    if (!window.confirm('Dừng và xóa hồ sơ này? Tệp đã tải sẽ bị gỡ.')) return
    setBusy(true)
    try {
      await deleteDossier(dossierId)
      const name = (detail?.name ?? passedName)?.trim()
      navigate(backTo, {
        state: {
          notice: name ? `Đã xóa hồ sơ “${name}”.` : 'Đã xóa hồ sơ.',
        },
      })
    } catch {
      setError('Không hủy được tiến trình.')
      setBusy(false)
    }
  }

  async function retry() {
    if (!dossierId || busy) return
    setBusy(true)
    setError(null)
    try {
      await restartDossierOcr(dossierId)
      setAttempt((value) => value + 1)
      setBusy(false)
    } catch (cause) {
      setError(restartOcrErrorMessage(cause))
      setBusy(false)
    }
  }

  const statusText = failed
    ? 'OCR thất bại'
    : ready
      ? 'Đã xử lý xong'
      : jobStatus === 'processing' || pageTotals.done > 0
        ? 'Đang xử lý tự động'
        : 'Đang chờ worker nhận tệp'

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <div className="flex flex-col gap-space-sm pt-space-md mb-gutter">
        <div className="flex items-center justify-between gap-space-md">
          <nav className="flex items-center gap-space-xs text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
            <Link className="hover:text-primary transition-colors" to={backTo}>
              {backLabel}
            </Link>
            <MaterialIcon name="chevron_right" className="text-[14px]" />
            <span className="text-on-surface font-semibold">
              Tiến trình nạp & phân tích tự động
            </span>
          </nav>
          <div className="flex items-center gap-space-sm bg-surface-container-low px-space-md py-space-xs rounded-lg shadow-sm">
            <span className="relative flex h-2 w-2">
              {ready || failed ? null : (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              )}
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  failed
                    ? 'bg-error'
                    : ready
                      ? 'bg-emerald-600'
                      : 'bg-emerald-600'
                }`}
              />
            </span>
            <span className="font-body-sm text-body-sm text-on-surface font-medium">
              {statusText}
            </span>
          </div>
        </div>
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-md mt-space-xs">
          <div className="flex flex-col gap-space-xs">
            {titleInHeader ? null : (
              <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
                Tiến trình phân tích hợp đồng
              </h1>
            )}
            <div className="flex flex-wrap items-center gap-x-space-md gap-y-space-xs text-on-surface-variant font-body-sm text-body-sm">
              <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                {detail?.name ?? passedName ?? 'Hồ sơ vừa tải'}
              </span>
              <span className="text-outline-variant">•</span>
              <span className="bg-surface-container px-space-sm py-0.5 rounded text-on-surface font-medium">
                {documents.length} tài liệu
              </span>
              {pageTotals.total > 0 ? (
                <>
                  <span className="text-outline-variant">•</span>
                  <span>{pageTotals.total} trang tài liệu</span>
                </>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {error ? (
        <p
          className="mb-gutter rounded-lg bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      <div className="w-full bg-surface-container-lowest rounded-lg p-gutter shadow-sm mb-gutter">
        <div className="flex items-center justify-between mb-space-md">
          <div className="flex items-center gap-space-sm">
            <MaterialIcon
              name="checklist"
              className="text-on-tertiary-container text-[20px]"
            />
            <span className="font-title-sm text-title-sm text-on-surface font-semibold">
              Các bước xử lý tự động
            </span>
          </div>
          <span className="font-body-sm text-body-sm text-on-tertiary-container font-medium">
            Tiến độ: {ready ? 'Đã hoàn thành' : `${percent}%`}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-space-md">
          <PhaseCard
            title="1. Tải tệp"
            status={documents.length > 0 ? 'done' : 'active'}
            detail={documents.length > 0 ? 'Hoàn tất' : 'Đang tải'}
          />
          <PhaseCard
            title="2. Nhận diện chữ"
            status={
              failed
                ? 'failed'
                : ready
                  ? 'done'
                  : documents.length > 0
                    ? 'active'
                    : 'waiting'
            }
            detail={
              failed
                ? 'Lỗi'
                : ready
                  ? 'Hoàn tất'
                  : pageTotals.total > 0
                    ? `${percent}%`
                    : 'Đang gửi tệp'
            }
            extra={
              pageTotals.total > 0
                ? `${pageTotals.done}/${pageTotals.total}`
                : undefined
            }
          />
          <PhaseCard
            title="3. Phân tích điều khoản"
            status={ready ? 'done' : 'waiting'}
            detail={ready ? 'Hoàn tất' : 'Chờ xử lý'}
          />
          <PhaseCard
            title="4. Hoàn tất"
            status={ready ? 'done' : 'waiting'}
            detail={ready ? 'Hoàn tất' : 'Chờ xử lý'}
            icon="folder_check"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-gutter">
        <div className="xl:col-span-7 flex flex-col gap-gutter">
          <section className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm">
            <div className="flex items-center justify-between mb-space-md pb-space-sm">
              <div className="flex items-center gap-space-sm">
                <MaterialIcon
                  name="description"
                  className="text-primary text-[20px]"
                />
                <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                  Tiến độ đọc tài liệu hồ sơ
                </span>
              </div>
              <span className="font-label-sm text-label-sm text-on-surface-variant">
                Tự động cập nhật
              </span>
            </div>
            <div className="flex flex-col gap-space-sm">
              {files.length === 0 ? (
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Đang lấy danh sách tệp từ hồ sơ.
                </p>
              ) : (
                files.map((file) => <FileRow key={file.id} file={file} />)
              )}
            </div>
          </section>
          <section className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm flex flex-col">
            <div className="flex items-center justify-between pb-space-sm mb-space-sm">
              <div className="flex items-center gap-space-sm">
                <MaterialIcon
                  name="history"
                  className="text-on-tertiary-container text-[20px]"
                />
                <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                  Nhật ký xử lý
                </span>
              </div>
              <span className="font-body-sm text-body-sm text-on-surface-variant">
                Theo trạng thái job trên backend
              </span>
            </div>
            <div className="flex flex-col gap-space-sm">
              {logs.length === 0 ? (
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Chưa có bước nào được ghi nhận.
                </p>
              ) : (
                logs.map((log) => <LogRow key={log.id} log={log} />)
              )}
            </div>
          </section>
        </div>
        <div className="xl:col-span-5 flex flex-col gap-gutter">
          <section className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm flex flex-col">
            <div className="flex items-center justify-between mb-space-md pb-space-sm">
              <div className="flex items-center gap-space-sm">
                <MaterialIcon
                  name="insights"
                  className="text-primary text-[20px]"
                />
                <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                  Thông tin ghi nhận
                </span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-space-sm mb-space-md">
              <div className="p-space-md rounded-lg bg-surface-container-low flex flex-col">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-medium">
                  Điều khoản
                </span>
                <span className="font-headline-lg text-headline-lg text-primary font-bold mt-space-xs">
                  {clauseCount ?? '—'}
                </span>
              </div>
              <div className="p-space-md rounded-lg bg-surface-container-low flex flex-col">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-medium">
                  Trang đã đọc
                </span>
                <span className="font-headline-md text-headline-md text-primary font-bold mt-space-xs">
                  {pageTotals.done}/{pageTotals.total || '—'}
                </span>
              </div>
            </div>
            <div className="mt-auto p-space-sm bg-surface-container-low rounded-lg flex items-center gap-space-sm">
              <MaterialIcon
                name="verified_user"
                className="text-on-tertiary-container text-[18px] shrink-0"
              />
              <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">
                Mã hóa riêng biệt & Bảo mật tuyệt đối
              </span>
            </div>
          </section>
        </div>
      </div>

      <div className="mt-gutter pt-space-md flex flex-col md:flex-row items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-md">
          {ready ? null : (
            <button
              className="font-body-sm text-body-sm text-error hover:underline flex items-center gap-space-xs disabled:opacity-60"
              disabled={busy || !dossierId}
              type="button"
              onClick={() => {
                void cancelJob()
              }}
            >
              <MaterialIcon name="close" className="text-[16px]" />
              <span>Hủy tiến trình này</span>
            </button>
          )}
          {failed ? (
            <button
              className="font-body-sm text-body-sm text-primary hover:underline flex items-center gap-space-xs disabled:opacity-60"
              disabled={busy}
              type="button"
              onClick={() => {
                void retry()
              }}
            >
              <MaterialIcon name="refresh" className="text-[16px]" />
              <span>Chạy lại OCR</span>
            </button>
          ) : null}
        </div>
        <button
          className={`flex items-center gap-space-sm px-gutter py-space-sm bg-primary text-on-primary rounded-lg font-title-sm text-title-sm shadow-sm transition-all ${
            ready
              ? 'hover:bg-primary-container cursor-pointer'
              : 'opacity-50 cursor-not-allowed'
          }`}
          disabled={!ready || !dossierId}
          type="button"
          onClick={() => {
            if (!ready || !dossierId) return
            navigate(structurePath(dossierId), {
              state: mode ? { structureMode: mode } : undefined,
            })
          }}
        >
          <span>Xem hồ sơ</span>
          <MaterialIcon name="arrow_forward" className="text-[18px]" />
        </button>
      </div>
    </div>
  )
}

function PhaseCard({
  title,
  status,
  detail,
  extra,
  icon = 'hourglass_empty',
}: {
  title: string
  status: 'done' | 'active' | 'waiting' | 'failed'
  detail: string
  extra?: string
  icon?: string
}) {
  const shell =
    status === 'done'
      ? 'bg-surface-container-low'
      : status === 'active'
        ? 'bg-surface-container-high'
        : 'bg-surface-container-lowest opacity-75'
  return (
    <div
      className={`flex flex-col p-space-md rounded-lg transition-all ${shell}`}
    >
      <div className="flex items-center justify-between mb-space-xs">
        <span className="font-title-sm text-title-sm text-on-surface font-bold">
          {title}
        </span>
        {status === 'done' ? (
          <div className="w-5 h-5 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700">
            <MaterialIcon name="check" className="text-[14px]" />
          </div>
        ) : null}
        {status === 'active' ? (
          <div className="w-5 h-5 rounded-full bg-primary-container flex items-center justify-center text-primary-fixed">
            <MaterialIcon
              name="progress_activity"
              className="text-[14px] animate-spin"
            />
          </div>
        ) : null}
        {status === 'failed' ? (
          <div className="w-5 h-5 rounded-full bg-error-container flex items-center justify-center text-error">
            <MaterialIcon name="error" className="text-[14px]" />
          </div>
        ) : null}
        {status === 'waiting' ? (
          <div className="w-5 h-5 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant">
            <MaterialIcon name={icon} className="text-[14px]" />
          </div>
        ) : null}
      </div>
      <div className="mt-auto flex items-center justify-between">
        <span
          className={`font-label-sm text-label-sm font-semibold ${
            status === 'done'
              ? 'text-emerald-700'
              : status === 'active'
                ? 'text-on-tertiary-container'
                : status === 'failed'
                  ? 'text-error'
                  : 'text-on-secondary-container font-medium'
          }`}
        >
          {detail}
        </span>
        {extra ? (
          <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">
            {extra}
          </span>
        ) : null}
      </div>
    </div>
  )
}

function FileRow({ file }: { file: FileRowModel }) {
  const rowClass =
    file.status === 'reading'
      ? 'bg-surface-container-high'
      : file.status === 'waiting'
        ? 'bg-surface-container-low opacity-80'
        : 'bg-surface-container-low'
  return (
    <div
      className={`flex items-center justify-between p-space-md rounded-lg ${rowClass}`}
    >
      <div className="flex items-center gap-space-sm min-w-0">
        {file.status === 'done' ? (
          <MaterialIcon
            name="check_circle"
            className="text-emerald-700 text-[20px] shrink-0"
          />
        ) : null}
        {file.status === 'reading' ? (
          <MaterialIcon
            name="progress_activity"
            className="text-on-tertiary-container text-[20px] animate-spin shrink-0"
          />
        ) : null}
        {file.status === 'waiting' ? (
          <MaterialIcon
            name="schedule"
            className="text-on-surface-variant text-[20px] shrink-0"
          />
        ) : null}
        {file.status === 'failed' ? (
          <MaterialIcon
            name="error"
            className="text-error text-[20px] shrink-0"
          />
        ) : null}
        <span className="font-title-sm text-title-sm text-on-surface truncate font-semibold">
          {file.name}
        </span>
        <span className="text-body-sm text-on-surface-variant">
          {file.meta}
        </span>
      </div>
      <span
        className={`font-body-sm text-body-sm font-semibold px-space-sm py-0.5 rounded shrink-0 ${
          file.status === 'done'
            ? 'text-emerald-800 bg-emerald-100'
            : file.status === 'reading'
              ? 'text-on-tertiary-container bg-surface-container'
              : file.status === 'failed'
                ? 'text-error bg-error-container'
                : 'text-on-secondary-container bg-surface-container'
        }`}
      >
        {file.label}
      </span>
    </div>
  )
}

function LogRow({ log }: { log: LogRowModel }) {
  return (
    <div
      className={`flex items-center gap-space-sm p-space-sm rounded-lg ${
        log.status === 'active'
          ? 'bg-surface-container-high'
          : 'bg-surface-container-low'
      }`}
    >
      {log.status === 'done' ? (
        <MaterialIcon
          name="check_circle"
          className="text-emerald-700 text-[18px] shrink-0"
        />
      ) : log.status === 'failed' ? (
        <MaterialIcon
          name="error"
          className="text-error text-[18px] shrink-0"
        />
      ) : (
        <MaterialIcon
          name="progress_activity"
          className="text-on-tertiary-container text-[18px] shrink-0 animate-spin"
        />
      )}
      <span className="font-body-sm text-body-sm text-on-surface font-semibold">
        {log.text}
      </span>
    </div>
  )
}
