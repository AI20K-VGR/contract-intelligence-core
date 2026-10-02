import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { loadDocumentPdf } from '../api/structure'
import type { ResolvedPart } from '../split/parts'
import { MaterialIcon } from './icons'

GlobalWorkerOptions.workerSrc = workerUrl

const THUMB_SCALE = 0.3
const ZOOM_SCALE = 1.6

type RenderLarge = (index: number, canvas: HTMLCanvasElement) => Promise<void>

function roleOfPage(parts: ResolvedPart[], page: number) {
  return parts.find((part) => page >= part.pageStart && page <= part.pageEnd)
}

function Thumb({
  page,
  render,
  part,
  partNo,
  disabled,
  onStartAnnex,
  onZoom,
}: {
  page: number
  render: ((canvas: HTMLCanvasElement) => Promise<void>) | null
  part: ResolvedPart | undefined
  partNo: number
  disabled: boolean
  onStartAnnex: (page: number) => void
  onZoom: (page: number) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [drawn, setDrawn] = useState(false)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !render) return
    let cancelled = false
    render(canvas)
      .then(() => {
        if (!cancelled) setDrawn(true)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [render])

  const annex = part?.role === 'annex'
  // Trang đầu của một phần phụ lục: nơi người dùng đã chọn điểm cắt.
  const startsAnnex = annex && part?.pageStart === page
  return (
    <figure className="flex w-32 shrink-0 flex-col gap-2">
      <div
        className={`relative overflow-hidden rounded-lg bg-white shadow-sm ring-2 ${
          annex ? 'ring-sky-400' : 'ring-amber-300'
        }`}
      >
        <canvas ref={canvasRef} className="block h-auto w-full" />
        {drawn ? null : (
          <span className="absolute inset-0 flex items-center justify-center bg-surface-container font-label-sm text-label-sm text-on-surface-variant">
            Đang tải…
          </span>
        )}
        <span
          className={`absolute left-1.5 top-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold text-white shadow ${
            annex ? 'bg-sky-600' : 'bg-amber-600'
          }`}
        >
          Phần {partNo}
        </span>
        <button
          aria-label={`Xem phóng to trang ${page}`}
          className="absolute left-1/2 top-1/2 flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-black/55 text-white shadow transition-colors hover:bg-black/80 focus:bg-black/80"
          type="button"
          onClick={() => onZoom(page)}
        >
          <MaterialIcon name="visibility" className="text-[20px]" />
        </button>
      </div>
      <figcaption className="flex flex-col gap-1.5">
        <span className="font-code-sm text-code-sm text-on-surface">
          Trang {page}
        </span>
        {startsAnnex ? (
          <span className="inline-flex items-center justify-center gap-1 rounded-md bg-sky-600 px-2 py-1 text-[12px] font-semibold text-white">
            Phụ lục bắt đầu
          </span>
        ) : page > 1 ? (
          <button
            className="rounded-md border border-sky-300 bg-sky-50 px-2 py-1 text-[12px] font-semibold text-sky-800 transition-colors hover:bg-sky-100 disabled:opacity-50"
            disabled={disabled}
            type="button"
            onClick={() => onStartAnnex(page)}
          >
            Phụ lục từ đây
          </button>
        ) : (
          <span className="px-2 py-1 text-[12px] text-on-surface-variant">
            Trang đầu
          </span>
        )}
      </figcaption>
    </figure>
  )
}

/** Trang phóng to giữa màn hình: bấm con mắt để mở, mũi tên để lật trang. */
function PagePreview({
  page,
  pageCount,
  renderLarge,
  onNavigate,
  onClose,
}: {
  page: number
  pageCount: number
  renderLarge: RenderLarge
  onNavigate: (page: number) => void
  onClose: () => void
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [drawn, setDrawn] = useState(false)
  const hasPrev = page > 1
  const hasNext = page < pageCount

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    let cancelled = false
    setDrawn(false)
    renderLarge(page - 1, canvas)
      .then(() => {
        if (!cancelled) setDrawn(true)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [page, renderLarge])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
      else if (event.key === 'ArrowLeft' && hasPrev) onNavigate(page - 1)
      else if (event.key === 'ArrowRight' && hasNext) onNavigate(page + 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [page, hasPrev, hasNext, onNavigate, onClose])

  const arrow =
    'flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white text-on-surface shadow-lg transition-colors hover:bg-surface-container disabled:opacity-30 disabled:hover:bg-white'

  return (
    <div
      aria-label={`Xem trang ${page}`}
      aria-modal="true"
      className="fixed inset-0 z-[900] flex items-center justify-center gap-space-md bg-black/60 p-space-lg"
      role="dialog"
      onClick={onClose}
    >
      <button
        aria-label="Trang trước"
        className={arrow}
        disabled={!hasPrev}
        type="button"
        onClick={(event) => {
          event.stopPropagation()
          onNavigate(page - 1)
        }}
      >
        <MaterialIcon name="chevron_left" className="text-[28px]" />
      </button>
      <div
        className="relative flex max-h-full flex-col items-center gap-2 rounded-xl bg-white p-3 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          aria-label="Đóng"
          className="absolute -right-3 -top-3 flex h-8 w-8 items-center justify-center rounded-full bg-black text-white shadow"
          type="button"
          onClick={onClose}
        >
          <MaterialIcon name="close" className="text-[18px]" />
        </button>
        <canvas
          ref={canvasRef}
          className="block max-h-[82vh] w-auto max-w-[min(80vw,60rem)]"
        />
        {drawn ? null : (
          <span className="absolute inset-0 flex items-center justify-center font-label-sm text-label-sm text-on-surface-variant">
            Đang tải…
          </span>
        )}
        <span className="rounded-full bg-black/70 px-3 py-0.5 font-code-sm text-code-sm text-white">
          Trang {page} / {pageCount}
        </span>
      </div>
      <button
        aria-label="Trang sau"
        className={arrow}
        disabled={!hasNext}
        type="button"
        onClick={(event) => {
          event.stopPropagation()
          onNavigate(page + 1)
        }}
      >
        <MaterialIcon name="chevron_right" className="text-[28px]" />
      </button>
    </div>
  )
}

/*
 * Xem trước từng trang của file gốc để chọn chỗ cắt. Chưa OCR nên chưa có ảnh
 * trang từ backend; vẽ thẳng từ PDF gốc (GET /documents/{id}/content) bằng pdf.js.
 */
export function SplitPageStrip({
  documentId,
  pageCount,
  parts,
  disabled,
  onStartAnnex,
}: {
  documentId: string
  pageCount: number
  parts: ResolvedPart[]
  disabled: boolean
  onStartAnnex: (page: number) => void
}) {
  const [error, setError] = useState<string | null>(null)
  const [renderers, setRenderers] = useState<
    ((canvas: HTMLCanvasElement) => Promise<void>)[] | null
  >(null)
  const [renderLarge, setRenderLarge] = useState<RenderLarge | null>(null)
  const [zoom, setZoom] = useState<number | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    let destroy: (() => Promise<void>) | null = null
    setError(null)
    setRenderers(null)
    setRenderLarge(null)
    setZoom(null)

    async function open() {
      const bytes = await loadDocumentPdf(documentId, controller.signal)
      if (cancelled) return
      const task = getDocument({ data: bytes.slice() })
      destroy = () => task.destroy()
      const pdf = await task.promise
      if (cancelled) return
      // Vẽ lần lượt để không chặn trình duyệt với file nhiều trang.
      let chain: Promise<unknown> = Promise.resolve()
      const next = Array.from({ length: pdf.numPages }, (_, index) => {
        return (canvas: HTMLCanvasElement) => {
          const job = chain.then(async () => {
            if (cancelled) return
            const page = await pdf.getPage(index + 1)
            const viewport = page.getViewport({ scale: THUMB_SCALE })
            canvas.width = viewport.width
            canvas.height = viewport.height
            await page.render({ canvas, viewport }).promise
          })
          chain = job.catch(() => undefined)
          return job
        }
      })
      setRenderers(next)
      setRenderLarge(() => async (index: number, canvas: HTMLCanvasElement) => {
        if (cancelled) return
        const page = await pdf.getPage(index + 1)
        const viewport = page.getViewport({ scale: ZOOM_SCALE })
        // Vẽ ra canvas tạm: React chạy effect hai lần (StrictMode) và pdf.js
        // từ chối hai lần render cùng lúc trên một canvas.
        const scratch = document.createElement('canvas')
        scratch.width = viewport.width
        scratch.height = viewport.height
        await page.render({ canvas: scratch, viewport }).promise
        if (cancelled) return
        canvas.width = scratch.width
        canvas.height = scratch.height
        canvas.getContext('2d')?.drawImage(scratch, 0, 0)
      })
    }

    open().catch((cause: unknown) => {
      if (cancelled || controller.signal.aborted) return
      setError(
        cause instanceof Error
          ? cause.message
          : 'Không xem trước được các trang.',
      )
    })

    return () => {
      cancelled = true
      controller.abort()
      void destroy?.().catch(() => undefined)
    }
  }, [documentId])

  if (error) {
    return (
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        {error} Bạn vẫn chia được bằng cách nhập số trang.
      </p>
    )
  }

  return (
    <div className="flex max-h-[34rem] flex-wrap gap-space-md overflow-y-auto p-1">
      {Array.from({ length: pageCount }, (_, index) => {
        const page = index + 1
        const part = roleOfPage(parts, page)
        const partNo = part ? parts.indexOf(part) + 1 : 0
        return (
          <Thumb
            key={page}
            disabled={disabled}
            page={page}
            partNo={partNo}
            render={renderers?.[index] ?? null}
            part={part}
            onStartAnnex={onStartAnnex}
            onZoom={setZoom}
          />
        )
      })}
      {zoom !== null && renderLarge ? (
        <PagePreview
          key={zoom}
          page={zoom}
          pageCount={pageCount}
          renderLarge={renderLarge}
          onClose={() => setZoom(null)}
          onNavigate={setZoom}
        />
      ) : null}
    </div>
  )
}
