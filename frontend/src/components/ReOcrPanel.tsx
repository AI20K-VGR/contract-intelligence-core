import { useEffect, useState } from 'react'
import {
  createReOcr,
  getReOcrRequest,
  isReOcrFinished,
  reOcrErrorMessage,
  REOCR_PROFILES,
  type ReOcrProfile,
  type ReOcrRequest,
} from '../api/reocr'
import { MaterialIcon } from './icons'

const STATUS_LABELS: Record<string, string> = {
  queued: 'Đang chờ',
  pending: 'Đang chờ',
  running: 'Đang OCR lại',
  processing: 'Đang OCR lại',
  completed: 'Đã xong',
  succeeded: 'Đã xong',
  failed: 'Lỗi',
  cancelled: 'Đã hủy',
}

const POLL_MS = 3000

type ReOcrPanelProps = {
  documentId: string
  /** Số trang đang chọn; rỗng nghĩa là chưa chọn trang nào. */
  selected: number[]
  onClear: () => void
  /** Gọi khi một yêu cầu kết thúc, để tải lại kết quả từng trang. */
  onFinished: () => void
}

export function ReOcrPanel({
  documentId,
  selected,
  onClear,
  onFinished,
}: ReOcrPanelProps) {
  const [profile, setProfile] = useState<ReOcrProfile>('high_res_binarize')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [request, setRequest] = useState<ReOcrRequest | null>(null)

  const requestId = request?.id
  const finished = request ? isReOcrFinished(request.status) : true

  useEffect(() => {
    if (!requestId || finished) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      getReOcrRequest(requestId, controller.signal)
        .then((next) => {
          if (controller.signal.aborted || !next) return
          setRequest(next)
          if (isReOcrFinished(next.status)) onFinished()
        })
        .catch((cause: unknown) => {
          if (controller.signal.aborted) return
          setError(reOcrErrorMessage(cause))
        })
    }, POLL_MS)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [requestId, finished, request, onFinished])

  async function submit() {
    if (busy || selected.length === 0) return
    setBusy(true)
    setError(null)
    try {
      const created = await createReOcr(documentId, {
        profile,
        pageNumbers: selected,
        reason,
      })
      setRequest(created)
      onClear()
      setReason('')
    } catch (cause) {
      setError(reOcrErrorMessage(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-space-sm border-b border-surface-container px-space-lg py-space-md">
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        Chọn các trang chữ bị sai rồi OCR lại bằng cấu hình khác. Kết quả cũ
        được giữ đến khi lần mới ghi xong.
      </p>
      <div className="flex flex-wrap items-end gap-space-sm">
        <label className="flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant">
          Cấu hình OCR
          <select
            className="h-9 rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-space-sm font-body-sm text-body-sm text-on-surface"
            value={profile}
            onChange={(event) => setProfile(event.target.value as ReOcrProfile)}
          >
            {REOCR_PROFILES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-48 flex-1 flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant">
          Lý do (tùy chọn)
          <input
            className="h-9 rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-space-sm font-body-sm text-body-sm text-on-surface"
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <button
          className="inline-flex h-9 items-center gap-space-xs rounded-lg bg-primary px-space-md font-label-md text-label-md text-on-primary disabled:opacity-50"
          disabled={busy || selected.length === 0}
          type="button"
          onClick={() => {
            void submit()
          }}
        >
          <MaterialIcon name="document_scanner" className="text-[18px]" />
          {busy
            ? 'Đang gửi…'
            : selected.length === 0
              ? 'Chọn trang để OCR lại'
              : `OCR lại ${selected.length} trang`}
        </button>
      </div>
      {error ? (
        <p className="font-body-sm text-body-sm text-error" role="alert">
          {error}
        </p>
      ) : null}
      {request ? (
        <p
          className="font-body-sm text-body-sm text-on-surface"
          role="status"
        >
          Yêu cầu OCR lại trang {request.pageNumbers.join(', ') || '—'}:{' '}
          <strong>
            {STATUS_LABELS[request.status.toLowerCase()] ?? request.status}
          </strong>
        </p>
      ) : null}
    </div>
  )
}
