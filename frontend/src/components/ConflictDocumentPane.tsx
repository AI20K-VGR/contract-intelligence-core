import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { loadDocumentPdf, type ClauseRegion } from '../api/structure'
import { MaterialIcon } from './icons'

GlobalWorkerOptions.workerSrc = workerUrl

export function ConflictDocumentPane({
  documentId,
  filename,
  pageNo,
  regions,
  citeNo,
  quote,
  title,
  onPageChange,
  onBack,
  onPageCount,
}: {
  documentId: string | null
  filename: string
  pageNo: number
  pageCount: number
  regions: ClauseRegion[]
  citeNo: number | null
  quote: string
  title: string
  onPageChange: (page: number) => void
  onBack: () => void
  onPageCount: (count: number) => void
}) {
  const canvasRefs = useRef<Array<HTMLCanvasElement | null>>([])
  const scrollerRef = useRef<HTMLDivElement>(null)
  const [rotation, setRotation] = useState(0)
  const [pageTotal, setPageTotal] = useState(0)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [finding, setFinding] = useState(false)
  const [findQuery, setFindQuery] = useState('')
  const [findNote, setFindNote] = useState<string | null>(null)

  useEffect(() => {
    if (!documentId) return
    const controller = new AbortController()
    let cancelled = false
    const tasks: Array<{ cancel: () => void }> = []
    setError(null)
    setReady(false)

    async function load() {
      const bytes = await loadDocumentPdf(documentId!, controller.signal)
      if (cancelled) return
      const loadingTask = getDocument({ data: bytes.slice() })
      try {
        const pdf = await loadingTask.promise
        if (cancelled) return
        onPageCount(pdf.numPages)
        setPageTotal(pdf.numPages)
      } finally {
        await loadingTask.destroy().catch(() => undefined)
      }
    }

    load().catch((cause: unknown) => {
      if (cancelled || controller.signal.aborted) return
      setError(
        cause instanceof Error
          ? cause.message
          : 'Không tải được file hợp đồng.',
      )
    })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [documentId, onPageCount])

  useEffect(() => {
    if (!documentId || pageTotal < 1) return
    const controller = new AbortController()
    let cancelled = false
    const tasks: Array<{ cancel: () => void }> = []

    async function paint() {
      const bytes = await loadDocumentPdf(documentId!, controller.signal)
      if (cancelled) return
      const loadingTask = getDocument({ data: bytes.slice() })
      try {
        const pdf = await loadingTask.promise
        if (cancelled) return
        for (let index = 1; index <= pdf.numPages; index += 1) {
          if (cancelled) return
          const canvas = canvasRefs.current[index - 1]
          if (!canvas) continue
          const page = await pdf.getPage(index)
          const viewport = page.getViewport({ scale: 1.4 })
          canvas.width = viewport.width
          canvas.height = viewport.height
          const context = canvas.getContext('2d')
          if (!context) throw new Error('Trình duyệt không vẽ được trang.')
          context.setTransform(1, 0, 0, 1, 0, 0)
          context.clearRect(0, 0, canvas.width, canvas.height)
          const task = page.render({ canvas, viewport })
          tasks.push(task)
          await task.promise
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
      for (const task of tasks) task.cancel()
      controller.abort()
    }
  }, [documentId, pageTotal])

  useEffect(() => {
    const node = scrollerRef.current?.querySelector(
      `[data-page="${pageNo}"]`,
    )
    node?.scrollIntoView({ block: 'start' })
  }, [pageNo, ready])

  async function download() {
    if (!documentId) return
    const bytes = await loadDocumentPdf(documentId)
    const blob = new Blob([bytes.slice()], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename || 'hop-dong.pdf'
    link.click()
    URL.revokeObjectURL(url)
  }

  async function findInDocument() {
    const needle = findQuery.trim().toLowerCase()
    if (!documentId || needle.length < 2) return
    setFindNote(null)
    const bytes = await loadDocumentPdf(documentId)
    const loadingTask = getDocument({ data: bytes.slice() })
    try {
      const pdf = await loadingTask.promise
      for (let index = 1; index <= pdf.numPages; index += 1) {
        const page = await pdf.getPage(index)
        const content = await page.getTextContent()
        const text = content.items
          .map((item) => ('str' in item ? item.str : ''))
          .join(' ')
          .toLowerCase()
        if (text.includes(needle)) {
          onPageChange(index)
          setFindNote(`Tìm thấy ở trang ${index}`)
          setFinding(false)
          return
        }
      }
      setFindNote('Không thấy cụm này trong PDF.')
    } finally {
      await loadingTask.destroy().catch(() => undefined)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-slate-200/70">
      <div className="flex h-11 shrink-0 items-center justify-between gap-space-sm border-b border-outline-variant/40 bg-surface-container-lowest px-space-md">
        <div className="flex min-w-0 items-center gap-space-sm">
          <button
            className="flex items-center gap-1 pr-space-xs font-label-sm text-label-sm text-secondary hover:text-on-surface"
            type="button"
            onClick={onBack}
          >
            <MaterialIcon name="arrow_back" className="text-[16px]" />
            <span className="hidden md:inline">Danh sách</span>
          </button>
          <div className="h-4 w-px bg-outline-variant/50" />
          <MaterialIcon
            name="picture_as_pdf"
            className="text-[18px] text-error"
          />
          <span
            className="max-w-[210px] truncate font-body-sm text-body-sm font-semibold text-on-surface"
            title={filename}
          >
            {filename || 'Hợp đồng'}
          </span>
          {citeNo ? (
            <span className="hidden whitespace-nowrap rounded bg-primary-container px-1.5 py-0.5 font-label-sm text-label-sm text-on-primary 2xl:inline-block">
              [{citeNo}] Đang rà soát
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-space-xs">
          <button
            className="flex h-7 w-7 items-center justify-center rounded text-secondary hover:bg-surface-container hover:text-on-surface"
            title="Xoay trang"
            type="button"
            onClick={() => setRotation((current) => (current + 90) % 360)}
          >
            <MaterialIcon name="rotate_right" className="text-[16px]" />
          </button>
          <button
            className="flex h-7 w-7 items-center justify-center rounded text-secondary hover:bg-surface-container hover:text-on-surface"
            title="Tìm trong PDF"
            type="button"
            onClick={() => setFinding((current) => !current)}
          >
            <MaterialIcon name="search" className="text-[16px]" />
          </button>
          <button
            className="flex h-7 w-7 items-center justify-center rounded text-secondary hover:bg-surface-container hover:text-on-surface disabled:opacity-40"
            disabled={!documentId}
            title="Tải văn bản"
            type="button"
            onClick={() => {
              download().catch(() => setError('Không tải được file hợp đồng.'))
            }}
          >
            <MaterialIcon name="download" className="text-[16px]" />
          </button>
        </div>
      </div>
      {finding ? (
        <form
          className="flex shrink-0 items-center gap-space-sm border-b border-outline-variant/30 bg-surface-container-lowest px-space-md py-1"
          onSubmit={(event) => {
            event.preventDefault()
            findInDocument().catch(() =>
              setFindNote('Không tìm được trong PDF.'),
            )
          }}
        >
          <input
            className="h-7 min-w-0 flex-1 rounded bg-surface-container-low px-2 font-body-sm text-body-sm text-on-surface outline-none focus:ring-1 focus:ring-primary-container"
            placeholder="Tìm cụm chữ trong PDF"
            value={findQuery}
            onChange={(event) => setFindQuery(event.target.value)}
          />
          <button
            className="h-7 rounded bg-primary-container px-2 font-label-sm text-label-sm text-on-primary"
            type="submit"
          >
            Tìm
          </button>
          {findNote ? (
            <span className="font-label-sm text-label-sm text-secondary">
              {findNote}
            </span>
          ) : null}
        </form>
      ) : null}
      <div
        ref={scrollerRef}
        className="flex min-h-0 flex-1 justify-center overflow-y-auto bg-slate-200/70 p-space-md lg:p-space-lg"
      >
        {documentId ? (
          <div className="w-full max-w-[690px]">
            {error ? (
              <p className="mb-3 font-body-sm text-body-sm text-error">{error}</p>
            ) : null}
            {!ready && !error ? (
              <p className="mb-3 font-body-sm text-body-sm text-secondary">
                Đang mở trang hợp đồng…
              </p>
            ) : null}
            <div
              className={ready ? '' : 'hidden'}
              style={{ transform: `rotate(${rotation}deg)` }}
            >
              {Array.from({ length: pageTotal }, (_, index) => {
                const page = index + 1
                const boxes = regions.filter((region) => {
                  if (region.pageNo !== page) return false
                  const [x0, y0, x1, y1] = region.bbox
                  const area = Math.max(0, x1 - x0) * Math.max(0, y1 - y0)
                  return area > 0 && area <= 1
                })
                return (
                  <div
                    key={page}
                    className="relative mx-auto mb-4 w-full bg-white shadow-[0_2px_12px_rgba(0,0,0,0.12)]"
                    data-page={page}
                  >
                    <canvas
                      ref={(node) => {
                        canvasRefs.current[index] = node
                      }}
                      className="block h-auto w-full"
                    />
                    {boxes.map((region, boxIndex) => (
                      <div
                        key={`${region.pageNo}-${boxIndex}`}
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
                )
              })}
            </div>
          </div>
        ) : (
          <article className="flex w-full max-w-[690px] flex-col border border-slate-300 bg-white p-space-lg font-serif text-[13px] leading-relaxed text-slate-900 shadow-[0_2px_12px_rgba(0,0,0,0.12)] md:p-12">
            <h4 className="mb-3 text-center font-sans text-[13px] font-bold uppercase tracking-tight text-primary-container">
              {title || 'Nội dung cần đối soát'}
            </h4>
            <p className="rounded border border-amber-300 bg-amber-100/90 p-2.5 font-sans font-medium leading-relaxed text-amber-950">
              {quote || 'Chưa có trích dẫn để đối chiếu.'}
            </p>
          </article>
        )}
      </div>
    </div>
  )
}
