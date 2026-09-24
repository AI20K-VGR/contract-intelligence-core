import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  deleteDossier,
  inspectDossierOcr,
  listDossiers,
  listDossiersErrorMessage,
  type DossierShareGrant,
  type DossierSummary,
  type OcrInspection,
  type OcrState,
} from '../api/dossiers'
import { ApiError } from '../api/client'
import { MaterialIcon } from '../components/icons'
import {
  dossierOpenTo,
  type Dossier,
  type DossierStatus,
} from '../data/dossiers'
import { dossiersLabel } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

type StatusFilter = 'all' | OcrState

const filters: { id: StatusFilter; label: string }[] = [
  { id: 'all', label: 'Tất cả' },
  { id: 'done', label: 'Đã OCR' },
  { id: 'running', label: 'Đang OCR' },
  { id: 'pending', label: 'Chưa OCR' },
  { id: 'error', label: 'OCR lỗi' },
]

const jobLabels: Record<string, string> = {
  uploaded: 'Đã tải lên',
  processing: 'Đang xử lý',
  extracted: 'Đã trích xuất',
  pending_review: 'Chờ rà soát',
  reviewed: 'Đã rà soát',
  approved: 'Đã duyệt',
  failed: 'Thất bại',
}

const dateTime = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function formatWhen(value: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return dateTime.format(date)
}

function metadataText(metadata: Record<string, unknown> | null, key: string) {
  const value = metadata?.[key]
  return typeof value === 'string' ? value.trim() : ''
}

function uiStatus(summary: DossierSummary): DossierStatus {
  const job = summary.latest_job_status
  const needsReview =
    job === 'pending_review' ||
    summary.has_conflicts ||
    summary.open_review_items > 0 ||
    summary.pending_conflicts > 0
  if (job === 'failed') return 'failed'
  if (needsReview) return 'review'
  if (job === 'extracted' || job === 'reviewed' || job === 'approved') {
    return 'ready'
  }
  return 'processing'
}

function reviewNote(summary: DossierSummary) {
  if (summary.pending_conflicts > 0) {
    return `${summary.pending_conflicts} điều khoản bất thường`
  }
  if (summary.open_review_items > 0) {
    return `${summary.open_review_items} mục chờ rà soát`
  }
  return undefined
}

function sharesOf(metadata: Record<string, unknown> | null): DossierShareGrant[] {
  const raw = metadata?.shared_with
  if (!Array.isArray(raw)) return []
  return raw.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const id = typeof row.id === 'string' ? row.id : ''
    if (!id) return []
    return [
      {
        id,
        email: typeof row.email === 'string' ? row.email : '',
        display_name:
          typeof row.display_name === 'string' ? row.display_name : '',
      },
    ]
  })
}

function accessScope(
  summary: DossierSummary,
  userId: string | undefined,
): Dossier['access'] {
  const metadata = summary.metadata
  const explicit = metadata?.access_scope
  if (
    explicit === 'mine' ||
    explicit === 'shared_out' ||
    explicit === 'shared_in'
  ) {
    return explicit
  }
  const owner = metadataText(summary.metadata, 'created_by')
  const shares = sharesOf(metadata)
  if (!owner || (userId && owner === userId)) {
    return shares.length > 0 ? 'shared_out' : 'mine'
  }
  if (userId && shares.some((item) => item.id === userId)) return 'shared_in'
  return 'mine'
}

export function dossierFromSummary(
  summary: DossierSummary,
  userId: string | undefined,
): Dossier {
  const code = metadataText(summary.metadata, 'code') || summary.id
  const job = summary.latest_job_status
  return {
    id: summary.id,
    title: summary.name,
    code,
    size: '',
    icon:
      summary.document_count && summary.document_count > 1
        ? 'folder_open'
        : 'folder',
    status: uiStatus(summary),
    progressLabel: job ? (jobLabels[job] ?? job) : 'Chưa có job',
    reviewNote: reviewNote(summary),
    documents: summary.document_count,
    updated: formatWhen(summary.created_at),
    access: accessScope(summary, userId),
    shares: sharesOf(summary.metadata),
    jobStatus: job,
    uploadedAt: summary.created_at,
  }
}

function textOf(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function countByOcr(
  items: Dossier[],
  ocrOf: (dossier: Dossier) => OcrState | 'checking',
  status?: OcrState,
) {
  if (!status) return items.length
  return items.filter((item) => ocrOf(item) === status).length
}

function StatusCell({
  dossier,
  ocr,
  detail,
  onRetry,
}: {
  dossier: Dossier
  ocr: OcrState | 'checking'
  detail: string | null
  onRetry: () => void
}) {
  const note = dossier.reviewNote ? (
    <span className="font-code-sm text-label-sm text-on-surface-variant">
      {dossier.reviewNote}
    </span>
  ) : null

  if (ocr === 'checking') {
    return (
      <span className="font-label-sm text-label-sm text-on-surface-variant">
        Đang kiểm tra OCR…
      </span>
    )
  }

  if (ocr === 'running') {
    return (
      <div className="flex flex-col gap-1">
        <Link
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-amber-100 text-amber-900 w-fit hover:opacity-80"
          to={`/ocr/${dossier.id}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-600 animate-pulse" />
          Đang OCR
        </Link>
        {note}
      </div>
    )
  }

  if (ocr === 'pending' || ocr === 'error') {
    const label = ocr === 'pending' ? 'Chưa OCR' : 'OCR lỗi'
    const action = ocr === 'pending' ? 'Tiếp tục OCR' : 'OCR lại'
    return (
      <div className="flex flex-col items-start gap-1">
        <div className="flex flex-wrap items-center gap-1">
          <Link
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold hover:opacity-80 ${
              ocr === 'pending'
                ? 'bg-amber-100 text-amber-950'
                : 'bg-error-container text-on-error-container'
            }`}
            to={`/ocr/${dossier.id}`}
          >
            {label}
          </Link>
          <button
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-surface-container text-on-surface hover:bg-surface-container-high"
            type="button"
            onClick={(event) => {
              event.stopPropagation()
              onRetry()
            }}
          >
            <MaterialIcon
              name={ocr === 'pending' ? 'play_arrow' : 'refresh'}
              className="text-[14px]"
            />
            {action}
          </button>
        </div>
        {detail ? (
          <span className="font-code-sm text-label-sm text-error">{detail}</span>
        ) : null}
        {note}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <Link
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-emerald-100 text-emerald-900 w-fit hover:opacity-80"
        to={`/ocr/${dossier.id}`}
      >
        <MaterialIcon name="check_circle" className="text-[14px]" />
        Đã OCR
      </Link>
      {note}
    </div>
  )
}

export const accessLabels: Record<Dossier['access'], string> = {
  mine: 'Hồ sơ của tôi',
  shared_out: 'Hồ sơ đã chia sẻ',
  shared_in: 'Hồ sơ được chia sẻ',
}

function AccessBadge({ dossier }: { dossier: Dossier }) {
  const shared = dossier.access !== 'mine'
  return (
    <Link
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-body-sm text-label-sm font-medium ${
        shared
          ? 'bg-surface-container-high text-on-tertiary-container'
          : 'bg-surface-container text-on-secondary-container'
      }`}
      to={`/quyen-truy-cap?dossier=${encodeURIComponent(dossier.id)}`}
      onClick={(event) => event.stopPropagation()}
    >
      <MaterialIcon
        name={shared ? 'share' : 'lock'}
        className="text-[14px]"
      />
      <span>{accessLabels[dossier.access]}</span>
    </Link>
  )
}

function DossierToolbar({
  dossiers,
  ocrOf,
  status,
  onStatusChange,
}: {
  dossiers: Dossier[]
  ocrOf: (dossier: Dossier) => OcrState | 'checking'
  status: StatusFilter
  onStatusChange: (value: StatusFilter) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-space-md flex-1">
      <div className="inline-flex items-center bg-surface-container-low p-1 rounded-lg gap-1">
        {filters.map((item) => {
          const active = status === item.id
          const count =
            item.id === 'all'
              ? countByOcr(dossiers, ocrOf)
              : countByOcr(dossiers, ocrOf, item.id)
          return (
            <button
              key={item.id}
              className={`px-3 py-1 rounded font-label-sm text-label-sm uppercase tracking-wide flex items-center gap-1.5 transition-colors ${
                active
                  ? 'bg-surface-container-lowest text-on-surface shadow-sm font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
              type="button"
              onClick={() => onStatusChange(item.id)}
            >
              {item.id === 'running' ? (
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              ) : null}
              {item.id === 'done' ? (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
              ) : null}
              {item.id === 'pending' ? (
                <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
              ) : null}
              {item.id === 'error' ? (
                <span className="w-1.5 h-1.5 rounded-full bg-error" />
              ) : null}
              <span>{item.label}</span>
              <span
                className={`font-code-sm text-[11px] ${
                  item.id === 'all' && active ? 'text-on-surface-variant' : ''
                }`}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function MyDossiersPage() {
  const { user } = useAuth()
  const heading = user ? dossiersLabel(user.role) : 'Hồ sơ'
  const navigate = useNavigate()
  usePageTitle(heading)
  const titleInHeader = useHeaderShowsPageTitle()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [reloadKey, setReloadKey] = useState(0)
  const [dossiers, setDossiers] = useState<Dossier[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Dossier | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [ocrById, setOcrById] = useState<Record<string, OcrInspection>>({})
  const [restartAt, setRestartAt] = useState<Record<string, number>>({})

  function ocrOf(dossier: Dossier): OcrState | 'checking' {
    const started = restartAt[dossier.id]
    const inspection = ocrById[dossier.id]
    if (
      started &&
      Date.now() - started < 25000 &&
      inspection?.state !== 'done'
    ) {
      return 'running'
    }
    if (inspection) return inspection.state
    if (dossier.jobStatus === 'processing') return 'running'
    return 'checking'
  }

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    listDossiers({ limit: 100, offset: 0, signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return
        setDossiers(result.items.map((item) => dossierFromSummary(item, user?.id)))
        setTotal(result.total)
      })
      .catch((cause: unknown) => {
        const message = listDossiersErrorMessage(cause)
        if (!message || controller.signal.aborted) return
        setDossiers([])
        setTotal(0)
        setError(message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [reloadKey])

  useEffect(() => {
    if (dossiers.length === 0) return
    const controller = new AbortController()
    let stopped = false

    async function inspect() {
      const entries = await Promise.all(
        dossiers.map(async (item) => {
          try {
            const inspection = await inspectDossierOcr(
              item.id,
              item.jobStatus ?? null,
              controller.signal,
            )
            return [item.id, inspection] as const
          } catch {
            if (controller.signal.aborted) return null
            const fallback: OcrInspection = {
              state: item.jobStatus === 'failed' ? 'error' : 'pending',
              detail: null,
            }
            return [item.id, fallback] as const
          }
        }),
      )
      if (stopped) return
      setOcrById((current) => {
        const next = { ...current }
        for (const entry of entries) {
          if (!entry) continue
          next[entry[0]] = entry[1]
        }
        return next
      })
      setRestartAt((current) => {
        const next = { ...current }
        for (const entry of entries) {
          if (!entry) continue
          if (entry[1].state === 'running' || entry[1].state === 'done') {
            delete next[entry[0]]
          }
        }
        return next
      })
    }

    void inspect()
    return () => {
      stopped = true
      controller.abort()
    }
  }, [dossiers])

  useEffect(() => {
    if (!dossiers.some((item) => ocrOf(item) === 'running')) return
    const timer = window.setTimeout(() => {
      setReloadKey((value) => value + 1)
    }, 4000)
    return () => window.clearTimeout(timer)
  }, [dossiers, ocrById, restartAt])

  async function confirmDelete() {
    if (!pendingDelete || deleting) return
    setDeleting(true)
    setError(null)
    try {
      await deleteDossier(pendingDelete.id)
      const removedId = pendingDelete.id
      setDossiers((current) => current.filter((item) => item.id !== removedId))
      setTotal((current) => Math.max(0, current - 1))
      setPendingDelete(null)
    } catch (cause: unknown) {
      if (cause instanceof ApiError && cause.status === 403) {
        setError('Bạn không có quyền xóa hồ sơ này.')
      } else {
        const message = listDossiersErrorMessage(cause)
        setError(message ?? 'Không xóa được hồ sơ. Thử lại.')
      }
      setPendingDelete(null)
    } finally {
      setDeleting(false)
    }
  }

  async function loadMore() {
    if (loadingMore || dossiers.length >= total) return
    setLoadingMore(true)
    setError(null)
    try {
      const result = await listDossiers({
        limit: 100,
        offset: dossiers.length,
      })
      setDossiers((current) => [
        ...current,
        ...result.items.map((item) => dossierFromSummary(item, user?.id)),
      ])
      setTotal(result.total)
    } catch (cause) {
      const message = listDossiersErrorMessage(cause)
      if (message) setError(message)
    } finally {
      setLoadingMore(false)
    }
  }

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return dossiers
      .filter((item) => {
        const matchesStatus = status === 'all' || ocrOf(item) === status
        const title = textOf(item.title)
        const code = textOf(item.code)
        const id = textOf(item.id)
        const matchesQuery =
          needle.length === 0 ||
          title.toLowerCase().includes(needle) ||
          code.toLowerCase().includes(needle) ||
          id.toLowerCase().includes(needle)
        return matchesStatus && matchesQuery
      })
      .sort((left, right) => {
        const delta =
          Date.parse(right.uploadedAt ?? '') - Date.parse(left.uploadedAt ?? '')
        return Number.isFinite(delta) ? delta : 0
      })
  }, [dossiers, ocrById, query, restartAt, status])

  function retryOcr(dossierId: string) {
    navigate(`/ocr/${dossierId}`, { state: { restart: true } })
  }

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-space-md pt-space-lg pb-space-lg">
        <div className="flex flex-col gap-space-xs">
          <div className="flex items-center gap-space-sm">
            {titleInHeader ? null : (
              <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
                {heading}
              </h1>
            )}
            <span className="px-2 py-0.5 rounded bg-surface-container text-on-surface-variant font-code-sm text-code-sm">
              {loading ? 'Đang tải…' : `${total} hồ sơ`}
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Quản lý, phân tích ngữ nghĩa và tra cứu tài liệu hợp đồng pháp lý cá
            nhân
          </p>
        </div>
        <div className="flex items-center gap-space-sm">
          <div className="relative w-[36rem] max-w-full">
            <MaterialIcon
              name="search"
              className="absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[18px]"
            />
            <input
              className="w-full h-9 pl-9 pr-space-md bg-surface-container-lowest text-on-surface placeholder:text-outline font-body-sm text-body-sm rounded shadow-[0_1px_2px_rgba(15,23,42,0.06)] focus:outline-none focus:ring-1 focus:ring-secondary"
              placeholder="Tìm kiếm theo tên, mã hồ sơ..."
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <button
            className="flex items-center gap-space-xs h-9 px-space-md bg-primary text-on-primary font-title-sm text-body-sm rounded shadow-sm hover:bg-primary-container transition-colors shrink-0"
            type="button"
            onClick={() => navigate('/tao-ho-so')}
          >
            <MaterialIcon name="cloud_upload" className="text-[18px]" />
            <span>Tải hồ sơ lên</span>
          </button>
        </div>
      </div>

      <div className="bg-surface-container-lowest rounded-lg shadow-[0_1px_3px_rgba(15,23,42,0.06)] flex flex-col overflow-hidden">
        <div className="p-space-md flex flex-col xl:flex-row xl:items-center justify-between gap-space-md bg-surface-container-lowest">
          <DossierToolbar
            dossiers={dossiers}
            ocrOf={ocrOf}
            status={status}
            onStatusChange={setStatus}
          />
        </div>

        <div className="w-full overflow-x-auto">
          <table className="w-full text-left font-body-sm text-body-sm border-collapse">
            <thead>
              <tr className="bg-surface-container-low text-on-secondary-container font-label-sm text-label-sm uppercase tracking-wider">
                <th className="py-3 px-space-md font-semibold w-[36%] min-w-[300px]">
                  Tên hồ sơ
                </th>
                <th className="py-3 px-space-md font-semibold w-[26%] min-w-[240px]">
                  Trạng thái & Tiến trình
                </th>
                <th className="py-3 px-space-md font-semibold w-[12%]">
                  Tải lên
                </th>
                <th className="py-3 px-space-md font-semibold w-[12%]">
                  Quyền truy cập
                </th>
                <th className="py-3 px-space-sm text-right pr-space-md font-semibold w-[4%]">
                  Thao tác
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-low text-on-surface">
              {error ? (
                <tr>
                  <td className="py-10 px-space-md" colSpan={5}>
                    <div className="flex flex-col items-start gap-space-sm">
                      <p
                        className="font-body-sm text-body-sm text-error"
                        role="alert"
                      >
                        {error}
                      </p>
                      <button
                        className="h-9 px-space-md rounded bg-surface-container text-on-surface font-label-sm text-label-sm"
                        type="button"
                        onClick={() => setReloadKey((value) => value + 1)}
                      >
                        Tải lại
                      </button>
                    </div>
                  </td>
                </tr>
              ) : null}
              {loading && dossiers.length === 0 ? (
                <tr>
                  <td
                    className="py-10 px-space-md text-on-surface-variant"
                    colSpan={5}
                  >
                    Đang tải lịch sử hồ sơ…
                  </td>
                </tr>
              ) : null}
              {!loading && !error && dossiers.length === 0 ? (
                <tr>
                  <td className="py-12 px-space-md" colSpan={5}>
                    <div className="flex flex-col items-center gap-space-sm text-center">
                      <MaterialIcon
                        name="folder_open"
                        className="text-secondary text-[28px]"
                      />
                      <p className="font-title-sm text-title-sm text-on-surface">
                        Chưa có hồ sơ tải lên
                      </p>
                      <p className="font-body-sm text-body-sm text-secondary">
                        Hồ sơ mới sẽ hiện ở đây sau khi tải lên.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : null}
              {!loading &&
              !error &&
              dossiers.length > 0 &&
              filtered.length === 0 ? (
                <tr>
                  <td
                    className="py-10 px-space-md text-on-surface-variant"
                    colSpan={5}
                  >
                    Không có hồ sơ khớp bộ lọc.
                  </td>
                </tr>
              ) : null}
              {filtered.map((dossier) => (
                <tr
                  key={dossier.id}
                  className={`transition-colors bg-surface-container-lowest ${
                    ocrOf(dossier) === 'running'
                      ? 'cursor-pointer hover:bg-surface-container-low'
                      : 'hover:bg-surface-container-low/70'
                  }`}
                  onClick={() => {
                    if (ocrOf(dossier) === 'running') {
                      navigate(`/ocr/${dossier.id}`)
                    }
                  }}
                >
                  <td className="py-3.5 px-space-md">
                    <div className="flex items-start gap-space-sm">
                      <MaterialIcon
                        name={dossier.icon}
                        className="text-primary-container text-[20px] mt-0.5 flex-shrink-0"
                      />
                      <div className="flex flex-col">
                        <Link
                          className="font-title-sm text-title-sm text-on-surface hover:text-on-tertiary-container cursor-pointer leading-tight font-semibold"
                          state={{
                            dossierId: dossier.id,
                            name: dossier.title,
                          }}
                          to={
                            ocrOf(dossier) === 'running'
                              ? `/ocr/${dossier.id}`
                              : dossierOpenTo(dossier)
                          }
                        >
                          {dossier.title}
                        </Link>
                        <span className="font-code-sm text-label-sm text-on-surface-variant mt-1 whitespace-nowrap">
                          {dossier.size
                            ? `${dossier.code} • ${dossier.size}`
                            : dossier.code}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 px-space-md">
                    <StatusCell
                      detail={ocrById[dossier.id]?.detail ?? null}
                      dossier={dossier}
                      ocr={ocrOf(dossier)}
                      onRetry={() => {
                        retryOcr(dossier.id)
                      }}
                    />
                  </td>
                  <td className="py-3.5 px-space-md whitespace-nowrap">
                    <span className="text-on-surface-variant text-body-sm">
                      {dossier.updated}
                    </span>
                  </td>
                  <td className="py-3.5 px-space-md whitespace-nowrap">
                    <AccessBadge dossier={dossier} />
                  </td>
                  <td className="py-3.5 px-space-sm text-right pr-space-md whitespace-nowrap">
                    <button
                      aria-label={`Xóa hồ sơ ${dossier.title}`}
                      className="p-1 hover:bg-error-container rounded text-on-surface-variant hover:text-error transition-colors"
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        setPendingDelete(dossier)
                      }}
                    >
                      <MaterialIcon name="delete" className="text-[18px]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && dossiers.length < total ? (
          <div className="p-space-md flex items-center justify-between gap-space-md border-t border-surface-container-low">
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              Đang hiện {dossiers.length} / {total} hồ sơ, mới nhất trước.
            </p>
            <button
              className="h-9 px-space-md rounded bg-surface-container text-on-surface font-label-sm text-label-sm disabled:opacity-50"
              disabled={loadingMore}
              type="button"
              onClick={() => {
                void loadMore()
              }}
            >
              {loadingMore ? 'Đang tải…' : 'Xem thêm'}
            </button>
          </div>
        ) : null}
      </div>
      {pendingDelete ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-space-md">
          <div
            className="w-full max-w-md bg-surface-container-lowest rounded shadow-lg p-space-lg flex flex-col gap-space-md"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-dossier-title"
          >
            <h2
              id="delete-dossier-title"
              className="font-title-sm text-title-sm text-on-surface"
            >
              Xóa hồ sơ
            </h2>
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              {pendingDelete.title} sẽ ẩn khỏi danh sách ngay. File và nội dung
              hợp đồng được xóa. Nhật ký người xóa và số token OCR được giữ lại.
            </p>
            <div className="flex justify-end gap-space-sm">
              <button
                className="h-9 px-space-md rounded bg-surface-container text-on-surface font-label-sm text-label-sm"
                disabled={deleting}
                type="button"
                onClick={() => setPendingDelete(null)}
              >
                Hủy
              </button>
              <button
                className="h-9 px-space-md rounded bg-error text-on-error font-label-sm text-label-sm disabled:opacity-50"
                disabled={deleting}
                type="button"
                onClick={() => {
                  void confirmDelete()
                }}
              >
                {deleting ? 'Đang xóa…' : 'Xóa'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
