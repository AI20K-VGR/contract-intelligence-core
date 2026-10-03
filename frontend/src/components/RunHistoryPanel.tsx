import { useCallback, useEffect, useState } from 'react'
import {
  cancelRun,
  isCancellableRun,
  listDossierRuns,
  reprocessDossier,
  runActionErrorMessage,
  runStatusLabel,
  type RunSummary,
} from '../api/runs'
import { MaterialIcon } from './icons'

const PAGE = 20

const whenFormat = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function formatWhen(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : whenFormat.format(date)
}

function formatDuration(seconds: number | null) {
  if (seconds === null) return '—'
  if (seconds < 60) return `${Math.round(seconds)} giây`
  return `${Math.floor(seconds / 60)} phút ${Math.round(seconds % 60)} giây`
}

function statusClass(status: string) {
  if (status === 'completed' || status === 'succeeded') {
    return 'bg-emerald-50 text-emerald-800'
  }
  if (status === 'failed' || status === 'dead') {
    return 'bg-error-container text-on-error-container'
  }
  if (status === 'cancelled') return 'bg-surface-container text-on-surface-variant'
  return 'bg-amber-50 text-amber-900'
}

type RunHistoryPanelProps = {
  dossierId: string
  /** Chỉ vận hành và quản trị được hủy hoặc chạy lại. */
  canManage: boolean
  /** Gọi sau khi mở run mới, để trang cha chuyển sang màn tiến độ. */
  onReprocessed?: () => void
}

export function RunHistoryPanel({
  dossierId,
  canManage,
  onReprocessed,
}: RunHistoryPanelProps) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    listDossierRuns(dossierId, { limit: PAGE, signal: controller.signal })
      .then((page) => {
        if (controller.signal.aborted) return
        setRuns(page.items)
        setTotal(page.total)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(runActionErrorMessage(cause))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [dossierId, reload])

  const loadMore = useCallback(async () => {
    if (loading) return
    setLoading(true)
    try {
      const page = await listDossierRuns(dossierId, {
        limit: PAGE,
        offset: runs.length,
      })
      setRuns((current) => [...current, ...page.items])
      setTotal(page.total)
    } catch (cause) {
      setError(runActionErrorMessage(cause))
    } finally {
      setLoading(false)
    }
  }, [dossierId, loading, runs.length])

  async function cancel(run: RunSummary) {
    if (busy) return
    if (!window.confirm('Hủy lần chạy này? Hồ sơ vẫn được giữ.')) return
    setBusy(run.runId)
    setError(null)
    try {
      await cancelRun(run.runId)
      setReload((value) => value + 1)
    } catch (cause) {
      setError(runActionErrorMessage(cause))
    } finally {
      setBusy(null)
    }
  }

  async function reprocess() {
    if (busy) return
    if (
      !window.confirm(
        'Chạy lại toàn bộ hồ sơ? Một lần chạy mới sẽ được tạo, các lần cũ vẫn được giữ.',
      )
    ) {
      return
    }
    setBusy('reprocess')
    setError(null)
    try {
      await reprocessDossier(dossierId)
      setReload((value) => value + 1)
      onReprocessed?.()
    } catch (cause) {
      setError(runActionErrorMessage(cause))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section
      aria-label="Lịch sử chạy"
      className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm space-y-space-md"
    >
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <div>
          <h2 className="font-headline-md text-headline-md text-on-surface">
            Lịch sử chạy
          </h2>
          <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
            Mỗi lần xử lý hồ sơ là một lần chạy riêng, không ghi đè lần trước.
          </p>
        </div>
        {canManage ? (
          <button
            className="inline-flex items-center gap-space-xs h-9 px-space-md rounded-lg bg-primary text-on-primary font-label-md text-label-md disabled:opacity-60"
            disabled={busy !== null}
            type="button"
            onClick={() => {
              void reprocess()
            }}
          >
            <MaterialIcon name="replay" className="text-[18px]" />
            {busy === 'reprocess' ? 'Đang gửi…' : 'Chạy lại toàn bộ'}
          </button>
        ) : null}
      </div>

      {error ? (
        <p className="font-label-sm text-label-sm text-error" role="alert">
          {error}
        </p>
      ) : null}

      {runs.length === 0 && !loading && !error ? (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Hồ sơ này chưa có lần chạy nào.
        </p>
      ) : null}

      <ul className="divide-y divide-outline-variant/20 rounded-lg border border-outline-variant/20">
        {runs.map((run, index) => (
          <li
            key={run.runId}
            className="flex flex-wrap items-center gap-space-md px-space-md py-space-sm"
          >
            <span className="font-code-sm text-code-sm text-secondary w-8">
              #{total - index}
            </span>
            <span
              className={`rounded px-space-xs py-0.5 font-label-sm text-label-sm font-semibold ${statusClass(run.status)}`}
            >
              {runStatusLabel(run.status)}
            </span>
            <span className="font-body-sm text-body-sm text-on-surface">
              {formatWhen(run.createdAt)}
            </span>
            <span className="font-body-sm text-body-sm text-secondary">
              {formatDuration(run.durationSeconds)}
            </span>
            <span
              className="font-code-sm text-code-sm text-secondary break-all"
              title={run.runId}
            >
              {run.runId}
            </span>
            {canManage && isCancellableRun(run.status) ? (
              <button
                className="ml-auto font-label-sm text-label-sm text-error hover:underline disabled:opacity-60"
                disabled={busy !== null}
                type="button"
                onClick={() => {
                  void cancel(run)
                }}
              >
                {busy === run.runId ? 'Đang hủy…' : 'Hủy lần chạy'}
              </button>
            ) : null}
          </li>
        ))}
      </ul>

      {runs.length < total ? (
        <button
          className="font-label-md text-label-md text-primary hover:underline disabled:opacity-60"
          disabled={loading}
          type="button"
          onClick={() => {
            void loadMore()
          }}
        >
          {loading ? 'Đang tải…' : `Xem thêm (${total - runs.length})`}
        </button>
      ) : null}
    </section>
  )
}
