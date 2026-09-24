import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import {
  contractDocument,
  countClauses,
  getDossierStructure,
  isOcrComplete,
  listClauses,
  listReviewSpots,
  loadDocumentLines,
  saveStructureMode,
  structureErrorMessage,
  type ClauseNode,
  type DossierStructure,
  type ReviewSpot,
} from '../api/structure'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { CitationPane } from '../components/CitationPane'
import { StructureMindmap } from '../components/StructureMindmap'
import { MaterialIcon } from '../components/icons'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'
import {
  buildStructureTree,
  parseStructureMode,
  structureModes,
  type OcrLine,
  type StructureMode,
} from '../structure'
import { citationNumbers, findClause } from '../structure/citations'

const jobLabels: Record<string, string> = {
  uploaded: 'Đã tải lên',
  processing: 'Đang OCR',
  extracted: 'Đã dựng cấu trúc',
  pending_review: 'Chờ rà soát',
  reviewed: 'Đã rà soát',
  approved: 'Đã duyệt',
  failed: 'OCR thất bại',
}

type Phase = 'loading' | 'ocr' | 'ready' | 'failed' | 'error'

function stateStructureMode(state: unknown): StructureMode | null {
  if (!state || typeof state !== 'object') return null
  return parseStructureMode(
    (state as { structureMode?: unknown }).structureMode,
  )
}

export function DossierStructurePage() {
  const titleInHeader = useHeaderShowsPageTitle()
  const { dossierId = '' } = useParams()
  const location = useLocation()
  const { user } = useAuth()
  const backTo = user ? dossiersPath(user.role) : '/'
  const backLabel = user ? dossiersLabel(user.role) : 'Hồ sơ'
  const [attempt, setAttempt] = useState(0)
  const [phase, setPhase] = useState<Phase>('loading')
  const [detail, setDetail] = useState<DossierStructure | null>(null)
  const [filename, setFilename] = useState<string | null>(null)
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [citeId, setCiteId] = useState<string | null>(null)
  // Dòng OCR thô: cây được dựng trên trình duyệt theo loại tài liệu.
  const [lines, setLines] = useState<OcrLine[] | null>(null)
  const [showLines, setShowLines] = useState(false)
  // Cây AI1 trả sẵn, chỉ dùng khi backend không trả được dòng OCR.
  const [fallbackNodes, setFallbackNodes] = useState<ClauseNode[]>([])
  const [mode, setMode] = useState<StructureMode | null>(
    stateStructureMode(location.state),
  )
  const [spots, setSpots] = useState<ReviewSpot[]>([])
  const [error, setError] = useState<string | null>(null)
  usePageTitle(detail?.name ?? 'Cấu trúc hợp đồng')

  const activeMode: StructureMode = mode ?? 'numbered'
  const nodes = useMemo(
    () => (lines ? buildStructureTree(lines, activeMode) : fallbackNodes),
    [lines, activeMode, fallbackNodes],
  )

  function changeMode(next: StructureMode) {
    if (next === activeMode) return
    setMode(next)
    if (!dossierId) return
    const metadata = detail?.metadata ?? null
    setDetail((current) =>
      current
        ? {
            ...current,
            structureMode: next,
            metadata: { ...(current.metadata ?? {}), structure_mode: next },
          }
        : current,
    )
    saveStructureMode(dossierId, metadata, next).catch(() => {
      // Cây đã dựng lại ngay trên trình duyệt. Lưu lựa chọn là bước phụ.
    })
  }

  useEffect(() => {
    if (!dossierId) {
      setPhase('error')
      setError('Thiếu mã hồ sơ.')
      return
    }

    const controller = new AbortController()
    let timer: number | undefined
    let stopped = false
    setSpots([])

    async function tick() {
      try {
        const next = await getDossierStructure(dossierId, controller.signal)
        if (stopped) return
        setDetail(next)
        setMode((current) => current ?? next.structureMode)
        setError(null)
        if (next.latestJobStatus === 'failed') {
          setPhase('failed')
          return
        }
        if (!isOcrComplete(next.latestJobStatus)) {
          setPhase('ocr')
          timer = window.setTimeout(() => {
            void tick()
          }, 2000)
          return
        }
        const document = contractDocument(next)
        if (!document) {
          setFilename(null)
          setDocumentId(null)
          setLines(null)
          setFallbackNodes([])
          setPhase('ready')
          return
        }
        let ocrLines: OcrLine[] = []
        try {
          ocrLines = await loadDocumentLines(document.id, controller.signal)
        } catch {
          if (controller.signal.aborted || stopped) return
          ocrLines = []
        }
        if (stopped) return
        if (ocrLines.length > 0) {
          setLines(ocrLines)
          setFallbackNodes([])
        } else {
          const tree = await listClauses(document.id, controller.signal)
          if (stopped) return
          setLines(null)
          setFallbackNodes(tree)
        }
        setFilename(document.filename)
        setDocumentId(document.id)
        setPhase('ready')
        try {
          const review = await listReviewSpots(dossierId, controller.signal)
          if (!stopped) setSpots(review)
        } catch {
          if (!stopped) setSpots([])
        }
      } catch (cause) {
        if (controller.signal.aborted || stopped) return
        const message = structureErrorMessage(cause)
        if (!message) return
        setError(message)
        setPhase('error')
      }
    }

    void tick()
    return () => {
      stopped = true
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [attempt, dossierId])

  const status = detail?.latestJobStatus
  const statusLabel = status ? (jobLabels[status] ?? status) : 'Đang chờ'
  const clauseCount = countClauses(nodes)
  const attentionIds = useMemo(() => {
    const ids = new Set<string>()
    for (const spot of spots) {
      for (const clauseId of spot.clauseIds) ids.add(clauseId)
    }
    return ids
  }, [spots])
  const needsCheck = status === 'pending_review' || spots.length > 0
  const citeOf = useMemo(() => citationNumbers(nodes), [nodes])
  const cited = citeId ? findClause(nodes, citeId) : null
  const frameRef = useRef<HTMLDivElement>(null)
  const [frameHeight, setFrameHeight] = useState<number | null>(null)

  useEffect(() => {
    function measure() {
      const node = frameRef.current
      if (!node) return
      const top = node.getBoundingClientRect().top
      const parent = node.parentElement
      const padBottom = parent
        ? Number.parseFloat(getComputedStyle(parent).paddingBottom) || 0
        : 0
      setFrameHeight(Math.max(420, window.innerHeight - top - padBottom))
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  return (
    <div
      ref={frameRef}
      data-structure-frame
      className="relative flex w-full flex-col overflow-hidden"
      style={frameHeight ? { height: frameHeight } : undefined}
    >
      <div
        className={
          cited || showLines
            ? 'flex min-h-0 flex-1'
            : 'min-h-0 flex-1 overflow-y-auto'
        }
      >
        <div
          className={
            cited || showLines
              ? 'min-h-0 min-w-0 flex-1 overflow-y-auto'
              : 'contents'
          }
        >
          <div className="flex shrink-0 flex-col gap-space-sm pt-space-md mb-space-md">
            <nav className="flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
              <Link
                className="hover:text-primary transition-colors"
                to={backTo}
              >
                {backLabel}
              </Link>
              <MaterialIcon name="chevron_right" className="text-[14px]" />
              <span className="text-on-surface font-semibold">
                Cấu trúc cây
              </span>
            </nav>
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-md">
              <div className="flex flex-col gap-space-xs max-w-3xl">
                {titleInHeader ? null : (
                  <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
                    {detail?.name ?? 'Cấu trúc hợp đồng'}
                  </h1>
                )}
                <p className="font-body-md text-body-md text-on-surface-variant">
                  {filename
                    ? `${filename} · ${clauseCount} nút`
                    : 'Hệ thống OCR hợp đồng rồi dựng cây điều khoản.'}
                </p>
              </div>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-label-sm text-label-sm font-semibold bg-surface-container text-secondary self-start">
                <span
                  className={`w-2 h-2 rounded-full ${
                    phase === 'ready'
                      ? 'bg-emerald-600'
                      : phase === 'failed' || phase === 'error'
                        ? 'bg-error'
                        : 'bg-amber-600'
                  }`}
                />
                {statusLabel}
              </span>
            </div>
          </div>

          {phase === 'loading' || phase === 'ocr' ? (
            <section className="bg-surface-container-lowest p-space-xl rounded-xl shadow-sm flex items-start gap-space-md">
              <MaterialIcon
                name="progress_activity"
                className="text-primary text-[22px] animate-spin"
              />
              <div className="flex flex-col gap-space-xs">
                <h2 className="font-title-sm text-title-sm text-primary">
                  Đang OCR và dựng cấu trúc
                </h2>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Trang này tự cập nhật. Cây hiện khi job sang trạng thái đã
                  trích xuất. Worker backend và AI1 cần đang chạy.
                </p>
              </div>
            </section>
          ) : null}

          {phase === 'failed' ? (
            <section
              className="bg-error-container text-on-error-container p-space-xl rounded-xl"
              role="alert"
            >
              <h2 className="font-title-sm text-title-sm">
                OCR không hoàn tất
              </h2>
              <p className="font-body-sm text-body-sm mt-space-xs">
                Hồ sơ đã nhận file, nhưng bước OCR trả lỗi. Kiểm tra worker và
                thử tải lại.
              </p>
            </section>
          ) : null}

          {phase === 'error' ? (
            <section
              className="bg-error-container text-on-error-container p-space-xl rounded-xl flex flex-col items-start gap-space-md"
              role="alert"
            >
              <p className="font-body-sm text-body-sm">{error}</p>
              <button
                className="h-10 px-space-lg bg-primary text-on-primary rounded-lg font-body-sm text-body-sm font-semibold"
                type="button"
                onClick={() => {
                  setPhase('loading')
                  setError(null)
                  setAttempt((current) => current + 1)
                }}
              >
                Thử lại
              </button>
            </section>
          ) : null}

          {phase === 'ready' && needsCheck ? (
            <Link
              className="mb-space-lg flex items-center justify-between gap-space-md rounded-xl bg-amber-50/80 px-space-lg py-space-md text-amber-950 hover:bg-amber-100 transition-colors"
              state={{
                dossierId,
                name: detail?.name,
              }}
              to="/doi-soat-xung-dot"
            >
              <span className="flex items-start gap-space-sm min-w-0">
                <MaterialIcon
                  name="warning"
                  className="text-[20px] mt-0.5 shrink-0"
                />
                <span className="flex flex-col gap-1 min-w-0">
                  <span className="font-title-sm text-title-sm font-semibold">
                    Cần kiểm tra
                    {spots.length > 0 ? ` · ${spots.length} chỗ` : ''}
                  </span>
                  <span className="font-body-sm text-body-sm">
                    {spots.length > 0
                      ? `${spots
                          .slice(0, 3)
                          .map((spot) => spot.topic)
                          .join(' · ')}. Bấm để mở giao diện kiểm tra.`
                      : 'Hồ sơ đã OCR xong và còn nội dung chờ rà soát. Bấm để mở giao diện kiểm tra.'}
                  </span>
                </span>
              </span>
              <MaterialIcon
                name="arrow_forward"
                className="text-[18px] shrink-0"
              />
            </Link>
          ) : null}

          {phase === 'ready' ? (
            <div className="mb-space-sm flex shrink-0 flex-col sm:flex-row sm:items-center justify-between gap-space-sm">
              <div className="flex items-center gap-space-sm">
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
                  Loại cấu trúc
                </span>
                <div
                  className="inline-flex items-center bg-surface-container p-1 gap-1"
                  role="radiogroup"
                  aria-label="Loại cấu trúc tài liệu"
                  style={{ borderRadius: '9999px' }}
                >
                  {structureModes.map((item) => {
                    const active = item.value === activeMode
                    return (
                      <button
                        key={item.value}
                        aria-checked={active}
                        className={`h-8 px-space-md font-body-sm text-body-sm font-semibold transition-colors ${
                          active
                            ? 'bg-primary text-on-primary shadow-sm'
                            : 'text-on-surface-variant hover:text-primary'
                        }`}
                        disabled={!lines}
                        role="radio"
                        style={{ borderRadius: '9999px' }}
                        title={item.hint}
                        type="button"
                        onClick={() => changeMode(item.value)}
                      >
                        {item.label}
                      </button>
                    )
                  })}
                </div>
              </div>
              {lines ? (
                <button
                  aria-expanded={showLines}
                  className={`font-code-sm text-code-sm underline-offset-2 hover:underline ${
                    showLines
                      ? 'text-primary'
                      : 'text-on-surface-variant hover:text-primary'
                  }`}
                  type="button"
                  onClick={() => {
                    setCiteId(null)
                    setShowLines((open) => !open)
                  }}
                >
                  Dựng từ {lines.length} dòng OCR trên trình duyệt
                </button>
              ) : (
                <span className="font-code-sm text-code-sm text-on-surface-variant">
                  Backend không trả dòng OCR, đang dùng cây AI1 trả sẵn
                </span>
              )}
            </div>
          ) : null}

          {phase === 'ready' ? (
            <div className="pb-16">
              <StructureMindmap
                attentionIds={attentionIds}
                citationOf={citeOf}
                focusId={citeId}
                nodes={nodes}
                subtitle={filename}
                title={detail?.name ?? 'Hợp đồng'}
                onCite={(id) => {
                  setShowLines(false)
                  setCiteId(id)
                }}
              />
            </div>
          ) : null}
        </div>
        {showLines && lines ? (
          <OcrLinesPane lines={lines} onClose={() => setShowLines(false)} />
        ) : null}
        {cited && documentId ? (
          <CitationPane
            key={cited.id}
            citeNo={citeOf.get(cited.id) ?? 0}
            documentId={documentId}
            node={cited}
            onClose={() => setCiteId(null)}
          />
        ) : null}
      </div>
    </div>
  )
}

function OcrLinesPane({
  lines,
  onClose,
}: {
  lines: OcrLine[]
  onClose: () => void
}) {
  const groups: { pageNo: number; lines: OcrLine[] }[] = []
  for (const line of lines) {
    const last = groups[groups.length - 1]
    if (!last || last.pageNo !== line.pageNo) {
      groups.push({ pageNo: line.pageNo, lines: [line] })
    } else {
      last.lines.push(line)
    }
  }
  let index = 0

  return (
    <aside className="flex w-[min(440px,46vw)] shrink-0 flex-col border-l border-surface-container bg-surface-container-lowest">
      <div className="flex items-center justify-between gap-space-sm border-b border-surface-container px-space-md py-space-sm">
        <div className="min-w-0">
          <p className="font-title-sm text-title-sm text-on-surface">
            {lines.length} dòng OCR
          </p>
          <p className="font-label-sm text-label-sm text-on-surface-variant">
            Đúng các dòng đang dùng để dựng cây, đủ chữ.
          </p>
        </div>
        <button
          aria-label="Đóng danh sách dòng OCR"
          className="flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container"
          type="button"
          onClick={onClose}
        >
          <MaterialIcon name="close" className="text-[18px]" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {groups.map((group) => (
          <section key={group.pageNo}>
            <h2 className="sticky top-0 bg-surface-container px-space-md py-1.5 font-label-sm text-label-sm text-on-surface-variant">
              Trang {group.pageNo}
            </h2>
            <ol>
              {group.lines.map((line) => {
                index += 1
                const order = index
                return (
                  <li
                    key={line.id}
                    className="flex gap-space-sm border-b border-surface-container-low px-space-md py-space-sm"
                  >
                    <span className="w-8 shrink-0 font-code-sm text-code-sm text-on-surface-variant">
                      {order}
                    </span>
                    <p className="min-w-0 flex-1 whitespace-pre-wrap font-body-sm text-body-sm text-on-surface">
                      {line.text}
                    </p>
                  </li>
                )
              })}
            </ol>
          </section>
        ))}
      </div>
    </aside>
  )
}
