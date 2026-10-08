import { useEffect, useRef, useState } from 'react'
import {
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
} from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { loadDocumentPdf } from '../api/structure'
import { MaterialIcon } from './icons'

GlobalWorkerOptions.workerSrc = workerUrl

/*
 * Tự vẽ PDF bằng pdf.js thay cho trình xem có sẵn của trình duyệt: trình xem đó
 * có nút gửi hợp đồng ra ngoài (tóm tắt AI của Chrome/Edge, lưu Google Drive)
 * mà không tắt riêng được. Ở đây chỉ có chuyển trang, phóng to/thu nhỏ, xoay,
 * tải xuống.
 */
const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3]

export type UploadedPdfFile = {
  id: string
  filename: string
  role: string
}

function roleLabel(role: string) {
  const normalized = role.toLowerCase()
  if (normalized === 'contract') return 'Hợp đồng chính'
  if (normalized === 'annex') return 'Phụ lục'
  return 'Tài liệu'
}

export function UploadedPdfPane({
  documentId,
  filename,
  files = [],
  onSelect,
  onClose,
}: {
  documentId: string
  filename: string | null
  files?: UploadedPdfFile[]
  onSelect?: (id: string) => void
  onClose: () => void
}) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null)
  const [pageNo, setPageNo] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState(0)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const viewRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl: string | null = null
    let loading: ReturnType<typeof getDocument> | null = null
    setError(null)
    setUrl(null)
    setPdf(null)
    setPageNo(1)
    setZoom(1)
    setRotation(0)

    loadDocumentPdf(documentId, controller.signal)
      .then(async (bytes) => {
        if (controller.signal.aborted) return
        objectUrl = URL.createObjectURL(
          new Blob([bytes.slice()], { type: 'application/pdf' }),
        )
        setUrl(objectUrl)
        loading = getDocument({ data: bytes.slice() })
        const loaded = await loading.promise
        if (controller.signal.aborted) return
        setPdf(loaded)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(
          cause instanceof Error ? cause.message : 'Không tải được file PDF.',
        )
      })

    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      void loading?.destroy()
    }
  }, [documentId])

  // Vẽ trang đang xem; 100% là vừa bề ngang khung.
  useEffect(() => {
    const canvas = canvasRef.current
    const view = viewRef.current
    if (!pdf || !canvas || !view) return
    let cancelled = false
    let task: { cancel: () => void } | null = null
    void (async () => {
      const page = await pdf.getPage(pageNo)
      if (cancelled) return
      const base = page.getViewport({ scale: 1, rotation })
      const width = Math.max(200, view.clientWidth - 32) * zoom
      const ratio = window.devicePixelRatio || 1
      const viewport = page.getViewport({
        scale: (width / base.width) * ratio,
        rotation,
      })
      canvas.width = viewport.width
      canvas.height = viewport.height
      canvas.style.width = `${width}px`
      const render = page.render({ canvas, viewport })
      task = render
      await render.promise.catch(() => undefined)
    })()
    return () => {
      cancelled = true
      task?.cancel()
    }
  }, [pdf, pageNo, zoom, rotation])

  const pages = pdf?.numPages ?? 0
  const zoomIndex = ZOOMS.indexOf(zoom)

  return (
    <aside className="flex h-full min-h-0 w-1/2 min-w-0 shrink-0 flex-col border-l border-outline-variant/30 bg-white">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-outline-variant/20 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-tone-900">
            PDF đã tải lên
          </p>
          <p className="truncate text-xs text-tone-500">
            {filename ?? 'File hợp đồng gốc'}
          </p>
        </div>
        <button
          aria-label="Đóng PDF"
          className="flex h-8 w-8 items-center justify-center rounded-full text-tone-500 hover:bg-tone-100"
          type="button"
          onClick={onClose}
        >
          <MaterialIcon name="close" className="text-[18px]" />
        </button>
      </div>
      {files.length > 1 && onSelect ? (
        <div className="flex shrink-0 gap-1 overflow-x-auto border-b border-outline-variant/20 px-3 py-2">
          {files.map((file) => {
            const active = file.id === documentId
            return (
              <button
                key={file.id}
                className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
                  active
                    ? 'bg-brand-100 text-brand-700 ring-1 ring-brand-200'
                    : 'bg-tone-100 text-tone-600 hover:bg-tone-200'
                }`}
                type="button"
                onClick={() => onSelect(file.id)}
              >
                {roleLabel(file.role)}
              </button>
            )
          })}
        </div>
      ) : null}
      <div className="min-h-0 flex-1 bg-tone-100">
        {error ? <p className="p-4 text-sm text-red-700">{error}</p> : null}
        {!pdf && !error ? (
          <p className="p-4 text-sm text-tone-500">Đang mở file PDF…</p>
        ) : null}
        {pdf ? (
          <div className="flex h-full min-h-0 flex-col">
            <div className="flex shrink-0 items-center justify-between gap-2 border-b border-outline-variant/20 bg-white px-3 py-1.5 text-sm text-tone-700">
              <div className="flex items-center gap-1">
                <ToolButton
                  disabled={pageNo <= 1}
                  icon="chevron_left"
                  label="Trang trước"
                  onClick={() => setPageNo((current) => current - 1)}
                />
                <span className="min-w-14 text-center tabular-nums">
                  {pageNo} / {pages}
                </span>
                <ToolButton
                  disabled={pageNo >= pages}
                  icon="chevron_right"
                  label="Trang sau"
                  onClick={() => setPageNo((current) => current + 1)}
                />
              </div>
              <div className="flex items-center gap-1">
                <ToolButton
                  disabled={zoomIndex <= 0}
                  icon="remove"
                  label="Thu nhỏ"
                  onClick={() => setZoom(ZOOMS[zoomIndex - 1] ?? zoom)}
                />
                <button
                  className="min-w-12 rounded px-1 text-center tabular-nums hover:bg-tone-100"
                  title="Vừa khung"
                  type="button"
                  onClick={() => setZoom(1)}
                >
                  {Math.round(zoom * 100)}%
                </button>
                <ToolButton
                  disabled={zoomIndex >= ZOOMS.length - 1}
                  icon="add"
                  label="Phóng to"
                  onClick={() => setZoom(ZOOMS[zoomIndex + 1] ?? zoom)}
                />
                <ToolButton
                  icon="rotate_right"
                  label="Xoay trang"
                  onClick={() =>
                    setRotation((current) => (current + 90) % 360)
                  }
                />
                {url ? (
                  <a
                    aria-label="Tải xuống"
                    className="flex h-8 w-8 items-center justify-center rounded hover:bg-tone-100"
                    download={filename ?? 'hop-dong.pdf'}
                    href={url}
                    title="Tải xuống"
                  >
                    <MaterialIcon name="download" className="text-[18px]" />
                  </a>
                ) : null}
              </div>
            </div>
            <div ref={viewRef} className="min-h-0 flex-1 overflow-auto p-4">
              <canvas
                ref={canvasRef}
                aria-label={`${filename ?? 'PDF'} · trang ${pageNo}`}
                className="mx-auto block bg-white shadow"
              />
            </div>
          </div>
        ) : null}
      </div>
    </aside>
  )
}

function ToolButton({
  icon,
  label,
  disabled = false,
  onClick,
}: {
  icon: string
  label: string
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      aria-label={label}
      className="flex h-8 w-8 items-center justify-center rounded hover:bg-tone-100 disabled:opacity-40 disabled:hover:bg-transparent"
      disabled={disabled}
      title={label}
      type="button"
      onClick={onClick}
    >
      <MaterialIcon name={icon} className="text-[18px]" />
    </button>
  )
}
