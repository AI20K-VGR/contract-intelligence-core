import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { loadDocumentPdf, type ClauseNode } from '../api/structure'
import { MaterialIcon } from './icons'

GlobalWorkerOptions.workerSrc = workerUrl

export function CitationPane({
  documentId,
  node,
  citeNo,
  onClose,
}: {
  documentId: string
  node: ClauseNode
  citeNo: number
  onClose: () => void
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

  return (
    <aside className="flex min-h-0 w-1/2 min-w-0 flex-col border-l border-outline-variant/30 bg-white">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-outline-variant/20 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">
            Trích dẫn {citeNo}
          </p>
          <p className="truncate text-xs text-slate-500">
            Trang {pageNo} · file đã tải lên
            {boxes.length === 0 ? ' · không có vùng tô' : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pages.length > 1 ? (
            <div className="flex items-center gap-1">
              {pages.map((page) => (
                <button
                  key={page}
                  className={`h-7 min-w-7 rounded-full px-2 text-xs font-semibold ${
                    page === pageNo
                      ? 'bg-[#0b1f3a] text-white'
                      : 'bg-slate-100 text-slate-700'
                  }`}
                  type="button"
                  onClick={() => setPageNo(page)}
                >
                  {page}
                </button>
              ))}
            </div>
          ) : null}
          <button
            className="flex h-8 w-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100"
            type="button"
            onClick={onClose}
          >
            <MaterialIcon name="close" className="text-[18px]" />
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto bg-slate-100 p-4">
        {error ? <p className="mb-3 text-sm text-red-700">{error}</p> : null}
        {!ready && !error ? (
          <p className="mb-3 text-sm text-slate-500">Đang mở trang hợp đồng…</p>
        ) : null}
        <div
          className={`relative mx-auto w-full max-w-3xl bg-white shadow ${ready ? '' : 'hidden'}`}
        >
          <canvas ref={canvasRef} className="block h-auto w-full" />
          {boxes.map((region, index) => (
            <div
              key={`${region.pageNo}-${index}`}
              className="pointer-events-none absolute border-2 border-amber-500 bg-amber-300/40"
              style={{
                left: `${region.bbox[0] * 100}%`,
                top: `${region.bbox[1] * 100}%`,
                width: `${(region.bbox[2] - region.bbox[0]) * 100}%`,
                height: `${(region.bbox[3] - region.bbox[1]) * 100}%`,
              }}
            />
          ))}
        </div>
      </div>
    </aside>
  )
}
