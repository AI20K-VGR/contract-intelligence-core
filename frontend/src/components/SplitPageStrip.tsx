import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { loadDocumentPdf } from '../api/structure'
import type { ResolvedPart } from '../split/parts'

GlobalWorkerOptions.workerSrc = workerUrl

const THUMB_SCALE = 0.3

function roleOfPage(parts: ResolvedPart[], page: number) {
  return parts.find((part) => page >= part.pageStart && page <= part.pageEnd)
}

function Thumb({
  page,
  render,
  role,
  partNo,
  disabled,
  onStartAnnex,
}: {
  page: number
  render: ((canvas: HTMLCanvasElement) => Promise<void>) | null
  role: 'contract' | 'annex' | undefined
  partNo: number
  disabled: boolean
  onStartAnnex: (page: number) => void
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

  const annex = role === 'annex'
  return (
    <figure className="flex w-28 shrink-0 flex-col gap-1">
      <div
        className={`relative overflow-hidden rounded border-2 bg-surface-container ${
          annex ? 'border-sky-500' : 'border-amber-500'
        }`}
      >
        <canvas ref={canvasRef} className="block h-auto w-full" />
        {drawn ? null : (
          <span className="absolute inset-0 flex items-center justify-center font-label-sm text-label-sm text-on-surface-variant">
            Đang tải…
          </span>
        )}
      </div>
      <figcaption className="flex flex-col gap-1">
        <span className="font-code-sm text-code-sm text-on-surface">
          Trang {page}
          <span
            className={`ml-1 font-label-sm text-label-sm ${
              annex ? 'text-sky-700' : 'text-amber-700'
            }`}
          >
            · Phần {partNo}
          </span>
        </span>
        <button
          className="rounded bg-surface-container-low px-1 py-0.5 text-left font-label-sm text-label-sm text-on-surface hover:bg-surface-container disabled:opacity-50"
          disabled={disabled || page <= 1}
          type="button"
          onClick={() => onStartAnnex(page)}
        >
          Phụ lục từ đây
        </button>
      </figcaption>
    </figure>
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

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    let destroy: (() => Promise<void>) | null = null
    setError(null)
    setRenderers(null)

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
    <div className="flex gap-space-sm overflow-x-auto pb-space-sm">
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
            role={part?.role}
            onStartAnnex={onStartAnnex}
          />
        )
      })}
    </div>
  )
}
