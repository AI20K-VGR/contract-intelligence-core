import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { loadDocumentPdf, type ClauseNode } from '../api/structure'
import {
  AUTO_ACCEPT_THRESHOLD,
  confidenceBoxClasses,
  confidenceLabels,
  confidenceLevel,
  formatConfidence,
  needsReview,
  REVIEW_THRESHOLD,
  type ConfidenceLevel,
} from '../structure/confidence'
import { MaterialIcon } from './icons'

GlobalWorkerOptions.workerSrc = workerUrl

const high = Math.round(AUTO_ACCEPT_THRESHOLD * 100)
const review = Math.round(REVIEW_THRESHOLD * 100)

/** Chú thích màu khung OCR: chấm màu + mức tin cậy. */
const LEGEND: { level: ConfidenceLevel; dot: string; range: string }[] = [
  { level: 'high', dot: 'bg-emerald-600', range: `≥ ${high}%` },
  { level: 'medium', dot: 'bg-amber-500', range: `${review}–${high - 1}%` },
  { level: 'low', dot: 'bg-red-600', range: `< ${review}%` },
]

export function CitationPane({
  documentId,
  node,
  citeNo,
  onClose,
  embedded = false,
  filename,
  banner,
}: {
  documentId: string
  node: ClauseNode
  citeNo: number
  onClose?: () => void
  embedded?: boolean
  filename?: string | null
  /** Thông báo dính dưới header (vd. điều khoản này có xung đột). */
  banner?: ReactNode
}) {
  const pages = [
    ...new Set(
      node.regions.length > 0
        ? node.regions.map((region) => region.pageNo)
        : [node.pageStart || 1],
    ),
  ].sort((a, b) => a - b)
  const [pageNo, setPageNo] = useState(pages[0] ?? 1)
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const [showBoxes, setShowBoxes] = useState(true)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const controller = new AbortController()
    let cancelled = false
    let renderTask: { cancel: () => void } | null = null
    setError(null)
    setReady(false)

    async function paint() {
      const bytes = await loadDocumentPdf(documentId, controller.signal)
      if (cancelled) return
      const loadingTask = getDocument({ data: bytes.slice() })
      try {
        const pdf = await loadingTask.promise
        if (cancelled) return
        const safePage = Math.min(Math.max(pageNo, 1), pdf.numPages)
        const page = await pdf.getPage(safePage)
        const viewport = page.getViewport({ scale: 1.5 })
        canvas.width = viewport.width
        canvas.height = viewport.height
        const context = canvas.getContext('2d')
        if (!context) throw new Error('Trình duyệt không vẽ được trang.')
        context.setTransform(1, 0, 0, 1, 0, 0)
        context.clearRect(0, 0, canvas.width, canvas.height)
        const task = page.render({ canvas, viewport })
        renderTask = task
        try {
          await task.promise
        } catch (cause) {
          if (cancelled) return
          throw cause
        }
        if (!cancelled) setReady(true)
      } finally {
        await loadingTask.destroy().catch(() => undefined)
      }
    }

    paint().catch((cause: unknown) => {
      if (cancelled || controller.signal.aborted) return
      setError(
        cause instanceof Error
          ? cause.message
          : 'Không tải được file hợp đồng.',
      )
    })

    return () => {
      cancelled = true
      renderTask?.cancel()
      controller.abort()
    }
  }, [documentId, pageNo])

  const boxes = node.regions.filter((region) => {
    if (region.pageNo !== pageNo) return false
    const [x0, y0, x1, y1] = region.bbox
    const area = Math.max(0, x1 - x0) * Math.max(0, y1 - y0)
    return area > 0 && area <= 1
  })
  const reviewCount = boxes.filter((region) => needsReview(region.confidence)).length

  return (
    <aside
      className={
        embedded
          ? 'flex min-h-0 min-w-0 flex-1 flex-col bg-surface-container-lowest'
          : 'flex min-h-0 w-1/2 min-w-0 flex-col border-l border-outline-variant/30 bg-white'
      }
    >
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-outline-variant/20 bg-surface-container px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <MaterialIcon name="picture_as_pdf" className="text-[18px] text-error" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-on-surface">
              {filename || `Trích dẫn ${citeNo}`}
            </p>
            <p className="truncate text-xs text-secondary">
              Trang {pageNo}
              {boxes.length === 0 ? ' · không có vùng tô' : ' · vùng trích dẫn được khoanh'}
              {reviewCount > 0 ? (
                <span className="font-semibold text-red-700">
                  {` · ${reviewCount} vùng cần review`}
                </span>
              ) : null}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {pages.length > 1 ? (
            <div className="flex items-center gap-1">
              {pages.map((page) => (
                <button
                  key={page}
                  className={`h-7 min-w-7 rounded-full px-2 text-xs font-semibold ${
                    page === pageNo
                      ? 'bg-brand-100 text-brand-700 ring-1 ring-brand-200'
                      : 'bg-tone-100 text-tone-700'
                  }`}
                  type="button"
                  onClick={() => setPageNo(page)}
                >
                  {page}
                </button>
              ))}
            </div>
          ) : null}
          {onClose ? (
            <button
              className="flex h-8 w-8 items-center justify-center rounded-full text-tone-500 hover:bg-tone-100"
              type="button"
              onClick={onClose}
            >
              <MaterialIcon name="close" className="text-[18px]" />
            </button>
          ) : null}
        </div>
      </div>
      {banner}
      {boxes.length > 0 ? (
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-outline-variant/20 px-4 py-1.5 text-xs text-on-surface-variant">
          <ul
            aria-label="Mức tin cậy OCR"
            className={`flex flex-wrap items-center gap-x-3 gap-y-1 ${showBoxes ? '' : 'opacity-50'}`}
          >
            {LEGEND.map((item) => (
              <li key={item.level} className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${item.dot}`} />
                {confidenceLabels[item.level]} {item.range}
              </li>
            ))}
          </ul>
          <button
            aria-checked={showBoxes}
            className="flex items-center gap-2 font-medium text-on-surface"
            role="switch"
            type="button"
            onClick={() => setShowBoxes((current) => !current)}
          >
            Khung OCR
            <span
              className={`relative h-4 w-7 rounded-full transition-colors ${showBoxes ? 'bg-brand-600' : 'bg-tone-300'}`}
            >
              <span
                className={`absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-all ${showBoxes ? 'left-3.5' : 'left-0.5'}`}
              />
            </span>
          </button>
        </div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-auto bg-tone-100 p-4">
        {error ? <p className="mb-3 text-sm text-red-700">{error}</p> : null}
        {!ready && !error ? (
          <p className="mb-3 text-sm text-tone-500">Đang mở trang hợp đồng…</p>
        ) : null}
        <div
          className={`relative mx-auto w-full max-w-3xl bg-white shadow ${ready ? '' : 'hidden'}`}
        >
          <canvas ref={canvasRef} className="block h-auto w-full" />
          {(showBoxes ? boxes : []).map((region, index) => {
            const confidence = region.confidence ?? null
            const level = confidence === null ? null : confidenceLevel(confidence)
            return (
              <div
                key={`${region.pageNo}-${index}`}
                className={`absolute border-2 ${
                  level ? confidenceBoxClasses[level] : 'border-amber-500 bg-amber-300/40'
                }`}
                title={
                  level && confidence !== null
                    ? `OCR ${formatConfidence(confidence)} · ${confidenceLabels[level]}`
                    : undefined
                }
                style={{
                  left: `${region.bbox[0] * 100}%`,
                  top: `${region.bbox[1] * 100}%`,
                  width: `${(region.bbox[2] - region.bbox[0]) * 100}%`,
                  height: `${(region.bbox[3] - region.bbox[1]) * 100}%`,
                }}
              />
            )
          })}
        </div>
      </div>
    </aside>
  )
}
