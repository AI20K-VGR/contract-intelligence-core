import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { loadDocumentPdf, type ClauseRegion } from '../api/structure'
import { MaterialIcon } from './icons'

GlobalWorkerOptions.workerSrc = workerUrl

export type ConflictDocumentFile = {
  id: string
  filename: string
  role: string
}

export type ConflictBox = ClauseRegion & { accent?: 'amber' | 'sky' }

function boxClass(accent: 'amber' | 'sky') {
  return accent === 'sky'
    ? 'border-sky-600 bg-sky-300/45'
    : 'border-amber-500 bg-amber-300/50'
}

function roleLabel(role: string) {
  const normalized = role.toLowerCase()
  if (normalized === 'contract') return 'Hợp đồng'
  if (normalized === 'annex') return 'Phụ lục'
  return 'Tài liệu'
}

export function ConflictDocumentPane({
  documentId,
  filename,
  files = [],
  pageNo,
  regions,
  citeNo,
  quote,
  title,
  sourceLabel,
  mark = 'amber',
  locked = false,
  locating = false,
  emptyNote = '',
  alignToken = 0,
  onPageChange,
  onBack,
  onPageCount,
  onSelectDocument,
}: {
  documentId: string | null
  filename: string
  files?: ConflictDocumentFile[]
  pageNo: number
  pageCount: number
  regions: ConflictBox[]
  citeNo: number | null
  quote: string
  title: string
  sourceLabel?: string
  mark?: 'amber' | 'sky'
  locked?: boolean
  locating?: boolean
  emptyNote?: string
  /** Tăng số này để kéo lại đúng vùng khoanh, kể cả khi vẫn đang ở trang đó. */
  alignToken?: number
  onPageChange: (page: number) => void
  onBack?: () => void
  onPageCount: (count: number) => void
  onSelectDocument?: (id: string) => void
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
  const [localPage, setLocalPage] = useState<number | null>(null)

  useEffect(() => {
    if (!documentId) return
    const controller = new AbortController()
    let cancelled = false
    setError(null)
    setReady(false)
    setPageTotal(0)

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
    setLocalPage(null)
  }, [documentId, pageNo])

  useEffect(() => {
    if (!ready) return
    const scroller = scrollerRef.current
    if (!scroller) return
    const page = localPage ?? pageNo
    let timer = 0
    const align = () => {
      const pageNode = scroller.querySelector<HTMLElement>(
        `[data-page="${page}"]`,
      )
      if (!pageNode) return
      const box = pageNode.querySelector<HTMLElement>('[data-citation-box]')
      const target = box ?? pageNode
      const delta =
        target.getBoundingClientRect().top -
        scroller.getBoundingClientRect().top
      scroller.scrollTop += delta - 8
    }
    const frame = requestAnimationFrame(() => {
      align()
      timer = window.setTimeout(align, 60)
    })
    return () => {
      cancelAnimationFrame(frame)
      window.clearTimeout(timer)
    }
  }, [alignToken, localPage, pageNo, ready, regions])

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
          setLocalPage(index)
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
    <div className="flex h-full min-h-0 flex-1 flex-col bg-slate-200/70">
      <div className="flex h-11 shrink-0 items-center justify-between gap-space-sm border-b border-outline-variant/40 bg-surface-container-lowest px-space-md">
        <div className="flex min-w-0 items-center gap-space-sm">
          {onBack ? (
            <button
              className="flex items-center gap-1 pr-space-xs font-label-sm text-label-sm text-secondary hover:text-on-surface"
              type="button"
              onClick={onBack}
            >
              <MaterialIcon name="arrow_back" className="text-[16px]" />
              <span className="hidden md:inline">Danh sách</span>
            </button>
          ) : null}
          {onBack ? <div className="h-4 w-px bg-outline-variant/50" /> : null}
          {sourceLabel ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded bg-surface-container px-1.5 py-0.5 font-label-sm text-label-sm font-semibold text-on-surface">
              <span
                className={`h-2.5 w-2.5 rounded-sm ${
                  mark === 'sky' ? 'bg-sky-500' : 'bg-amber-500'
                }`}
              />
              {sourceLabel}
            </span>
          ) : null}
          {files.length > 0 && !locked ? (
            <div className="flex min-w-0 items-center gap-1 overflow-x-auto">
              {files.map((file) => {
                const active = file.id === documentId
                return (
                  <button
                    key={file.id}
                    className={`flex h-7 max-w-[220px] shrink-0 items-center gap-1 rounded px-2 font-body-sm text-body-sm ${
                      active
                        ? 'bg-primary text-on-primary'
                        : 'text-on-surface hover:bg-surface-container'
                    }`}
                    title={`${roleLabel(file.role)} · ${file.filename}`}
                    type="button"
                    onClick={() => onSelectDocument?.(file.id)}
                  >
                    <MaterialIcon
                      name="picture_as_pdf"
                      className={`text-[16px] ${active ? '' : 'text-error'}`}
                    />
                    <span className="truncate">{file.filename}</span>
                  </button>
                )
              })}
            </div>
          ) : (
            <>
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
            </>
          )}
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
            {ready && locating ? (
              <p className="mb-3 font-body-sm text-body-sm text-secondary">
                Đang khoanh câu trích trên trang…
              </p>
            ) : null}
            {ready && !locating && regions.length === 0 && (emptyNote || quote) ? (
              <p
                className={`mb-3 rounded border px-2 py-1 font-body-sm text-body-sm ${
                  mark === 'sky'
                    ? 'border-sky-300 bg-sky-50 text-sky-950'
                    : 'border-amber-300 bg-amber-50 text-amber-950'
                }`}
              >
                {emptyNote || 'Chưa khoanh được câu trích trên tài liệu này.'}
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
                        key={`${region.pageNo}-${boxIndex}-${region.accent ?? mark}`}
                        data-citation-box
                        className={`pointer-events-none absolute z-10 border-2 ${boxClass(region.accent ?? mark)}`}
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
