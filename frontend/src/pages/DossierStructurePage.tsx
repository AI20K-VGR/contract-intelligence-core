import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
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
  searchDossier,
  structureErrorMessage,
  type DossierSearchResult,
  type ClauseNode,
  type DossierStructure,
  type ReviewSpot,
} from '../api/structure'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { CitationPane } from '../components/CitationPane'
import { StructureDocument } from '../components/StructureDocument'
import { StructureMindmap } from '../components/StructureMindmap'
import { StructureOutline } from '../components/StructureOutline'
import { TableStructure } from '../components/TableStructure'
import { MaterialIcon } from '../components/icons'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'
import {
  buildStructureTree,
  parseStructureMode,
  parseStructureView,
  STRUCTURE_VIEW_KEY,
  structureModes,
  structureViews,
  type OcrLine,
  type StructureMode,
  type StructureView,
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

/** Kiểu xem nhớ theo trình duyệt; mặc định sơ đồ tư duy. */
function storedStructureView(): StructureView {
  try {
    return (
      parseStructureView(window.localStorage.getItem(STRUCTURE_VIEW_KEY)) ??
      'mindmap'
    )
  } catch {
    return 'mindmap'
  }
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
  const [tableCite, setTableCite] = useState<{
    node: ClauseNode
    citeNo: number
  } | null>(null)
  // Dòng OCR thô: cây được dựng trên trình duyệt theo loại tài liệu.
  const [lines, setLines] = useState<OcrLine[] | null>(null)
  const [showLines, setShowLines] = useState(false)
  // Cây AI1 trả sẵn, chỉ dùng khi backend không trả được dòng OCR.
  const [fallbackNodes, setFallbackNodes] = useState<ClauseNode[]>([])
  const [mode, setMode] = useState<StructureMode | null>(
    stateStructureMode(location.state),
  )
  const [view, setView] = useState<StructureView>(storedStructureView)
  const [spots, setSpots] = useState<ReviewSpot[]>([])
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchResult, setSearchResult] = useState<DossierSearchResult | null>(
    null,
  )
  const [searchError, setSearchError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  usePageTitle(detail?.name ?? 'Cấu trúc hợp đồng')

  const activeMode: StructureMode = mode ?? 'numbered'
  const nodes = useMemo(
    () => (lines ? buildStructureTree(lines, activeMode) : fallbackNodes),
    [lines, activeMode, fallbackNodes],
  )
  useEffect(() => {
    setQuery('')
    setSearchResult(null)
    setSearchError(null)
  }, [dossierId])

  async function submitSearch(event: FormEvent) {
    event.preventDefault()
    const question = query.trim()
    if (!dossierId || !question || searching) return
    setSearching(true)
    setSearchError(null)
    try {
      setSearchResult(await searchDossier(dossierId, question))
    } catch (cause: unknown) {
      setSearchResult(null)
      setSearchError(
        structureErrorMessage(cause) ?? 'Không hỏi được hồ sơ này. Thử lại.',
      )
    } finally {
      setSearching(false)
    }
  }

  function changeView(next: StructureView) {
    setView(next)
    try {
      window.localStorage.setItem(STRUCTURE_VIEW_KEY, next)
    } catch {
      // Không lưu được cũng không sao; chỉ mất ghi nhớ giữa các phiên.
    }
  }

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
  const splitView = Boolean(cited || tableCite || showLines)
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
      className="relative flex w-full flex-col overflow-hidden bg-surface"
      style={frameHeight ? { height: frameHeight } : undefined}
    >
      <div
        className={
          splitView
            ? 'flex min-h-0 flex-1 overflow-auto'
            : 'flex min-h-0 flex-1 flex-col overflow-auto'
        }
      >
        <div
          className={
            splitView
              ? 'flex min-h-0 min-w-0 flex-1 flex-col overflow-auto'
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
            <div className="flex flex-col gap-space-sm md:flex-row md:items-start md:justify-between">
              <div className="flex min-w-0 flex-col gap-space-xs">
                {titleInHeader ? null : (
                  <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
                    {detail?.name ?? 'Cấu trúc hợp đồng'}
                  </h1>
                )}
                {/* Dòng meta: tệp · số nút · nguồn OCR · trạng thái */}
                <div className="flex flex-wrap items-center gap-x-space-sm gap-y-1 font-body-sm text-body-sm text-on-surface-variant">
                  {filename ? (
                    <span className="inline-flex min-w-0 items-center gap-1.5">
                      <MaterialIcon
                        name="description"
                        className="text-outline"
                        style={{ fontSize: 16 }}
                      />
                      <span className="truncate font-medium text-on-surface">
                        {filename}
                      </span>
                    </span>
                  ) : (
                    <span>
                      {activeMode === 'tables'
                        ? 'Các bảng mà OCR đã trích từ hợp đồng.'
                        : 'Hệ thống OCR hợp đồng rồi dựng cây điều khoản.'}
                    </span>
                  )}
                  {filename && phase === 'ready' ? (
                    <>
                      <MetaDot />
                      <span>
                        {activeMode === 'tables'
                          ? 'các bảng OCR đã trích'
                          : `${clauseCount} nút`}
                      </span>
                    </>
                  ) : null}
                  {phase === 'ready' ? (
                    <>
                      <MetaDot />
                      {lines ? (
                        <button
                          aria-expanded={showLines}
                          className={`inline-flex items-center gap-1 underline-offset-2 transition-colors hover:text-primary hover:underline ${
                            showLines ? 'text-primary' : ''
                          }`}
                          title="Xem các dòng OCR đang dùng để dựng cây"
                          type="button"
                          onClick={() => {
                            setCiteId(null)
                            setShowLines((open) => !open)
                          }}
                        >
                          {lines.length} dòng OCR
                          <MaterialIcon
                            name={showLines ? 'close' : 'open_in_new'}
                            style={{ fontSize: 14 }}
                          />
                        </button>
                      ) : (
                        <span title="Backend không trả dòng OCR">
                          cây AI1 trả sẵn
                        </span>
                      )}
                    </>
                  ) : null}
                  <MetaDot />
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-container px-2 py-0.5 font-label-sm text-label-sm font-semibold text-secondary">
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
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
              {phase === 'ready' ? (
                <form
                  className="relative w-full shrink-0 md:w-80 lg:w-96"
                  onSubmit={(event) => void submitSearch(event)}
                >
                  <MaterialIcon
                    name="search"
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-outline"
                  />
                  <input
                    aria-label="Hỏi về hợp đồng"
                    className="h-10 w-full rounded-full border border-outline-variant/30 bg-surface-container-lowest pl-9 pr-space-md font-body-sm text-body-sm text-on-surface shadow-[0_1px_2px_rgba(15,23,42,0.06)] placeholder:text-outline focus:outline-none focus:ring-1 focus:ring-secondary"
                    placeholder="Hỏi về hợp đồng này…"
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                </form>
              ) : null}
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
            <div className="mb-space-sm flex shrink-0 flex-wrap items-stretch gap-x-space-lg gap-y-space-sm rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-space-md py-space-sm shadow-sm">
              <ToolbarGroup label="Loại cấu trúc">
                <div
                  aria-label="Loại cấu trúc tài liệu"
                  className="inline-flex items-center gap-0.5 rounded-full bg-surface-container p-1"
                  role="radiogroup"
                >
                  {structureModes.map((item) => (
                    <SegmentButton
                      key={item.value}
                      active={item.value === activeMode}
                      disabled={item.value === 'tables' ? !documentId : !lines}
                      hint={item.hint}
                      icon={item.icon}
                      label={item.short}
                      onClick={() => changeMode(item.value)}
                    />
                  ))}
                </div>
              </ToolbarGroup>
              {activeMode !== 'tables' ? (
                <>
                  <span
                    aria-hidden
                    className="hidden w-px self-stretch bg-outline-variant/30 sm:block"
                  />
                  <ToolbarGroup label="Kiểu xem">
                    <div
                      aria-label="Kiểu xem cấu trúc"
                      className="inline-flex items-center gap-0.5 rounded-full bg-surface-container p-1"
                      role="radiogroup"
                    >
                      {structureViews.map((item) => (
                        <SegmentButton
                          key={item.value}
                          active={item.value === view}
                          hint={item.hint}
                          icon={item.icon}
                          label={item.label}
                          onClick={() => changeView(item.value)}
                        />
                      ))}
                    </div>
                  </ToolbarGroup>
                </>
              ) : null}
            </div>
          ) : null}

          {phase === 'ready' && (searching || searchError || searchResult) ? (
            <section className="mb-space-md rounded-xl bg-surface-container-lowest px-space-md py-space-md shadow-sm">
              {searching ? (
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Đang hỏi backend…
                </p>
              ) : null}
              {searchError ? (
                <p className="font-body-sm text-body-sm text-on-error-container">
                  {searchError}
                </p>
              ) : null}
              {searchResult ? (
                <div className="flex flex-col gap-space-xs">
                  <p className="font-label-sm text-label-sm text-on-surface-variant">
                    {searchResult.query}
                  </p>
                  <p className="font-body-sm text-body-sm text-on-surface">
                    {searchResult.answer
                      ? searchResult.answer
                      : searchResult.connected
                        ? 'AI2 không trả lời cho câu hỏi này.'
                        : 'AI2 chưa nối. Câu hỏi đã gửi tới backend, chưa có câu trả lời.'}
                  </p>
                  {searchResult.hits.length > 0 ? (
                    <ul className="flex flex-col gap-1">
                      {searchResult.hits.map((hit) => (
                        <li
                          key={`${hit.pageNo ?? ''}-${hit.text}`}
                          className="font-body-sm text-body-sm text-on-surface-variant"
                        >
                          {hit.pageNo ? `Trang ${hit.pageNo} · ` : ''}
                          {hit.text}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </section>
          ) : null}

          {phase === 'ready' && activeMode === 'tables' && documentId ? (
            <TableStructure
              activeId={tableCite?.node.id}
              documentId={documentId}
              query=""
              onCite={(node, citeNo) => {
                setShowLines(false)
                setCiteId(null)
                setTableCite({ node, citeNo })
              }}
            />
          ) : null}

          {phase === 'ready' && activeMode !== 'tables' ? (
            <div className="flex min-h-[520px] flex-1 flex-col pb-space-md">
              {(() => {
                const shared = {
                  attentionIds,
                  citationOf: citeOf,
                  focusId: citeId,
                  nodes,
                  title: detail?.name ?? 'Hợp đồng',
                  onCite: (id: string) => {
                    setShowLines(false)
                    setTableCite(null)
                    setCiteId(id)
                  },
                }
                switch (view) {
                  case 'outline':
                    return <StructureOutline {...shared} />
                  case 'document':
                    return <StructureDocument {...shared} />
                  case 'tree':
                    return (
                      <StructureMindmap
                        key="tree"
                        {...shared}
                        orientation="vertical"
                        subtitle={filename}
                      />
                    )
                  default:
                    // key để đổi hướng thì dựng lại, tự căn vừa khung.
                    return (
                      <StructureMindmap
                        key="mindmap"
                        {...shared}
                        subtitle={filename}
                      />
                    )
                }
              })()}
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
        ) : tableCite && documentId && activeMode === 'tables' ? (
          <CitationPane
            key={tableCite.node.id}
            citeNo={tableCite.citeNo}
            documentId={documentId}
            node={tableCite.node}
            onClose={() => setTableCite(null)}
          />
        ) : null}
      </div>
    </div>
  )
}

function MetaDot() {
  return (
    <span aria-hidden className="h-1 w-1 rounded-full bg-outline-variant" />
  )
}

/** Một nhóm trong thanh công cụ: nhãn nhỏ phía trên, điều khiển bên dưới. */
function ToolbarGroup({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
        {label}
      </span>
      {children}
    </div>
  )
}

function SegmentButton({
  active,
  disabled,
  icon,
  label,
  hint,
  onClick,
}: {
  active: boolean
  disabled?: boolean
  icon: string
  label: string
  hint?: string
  onClick: () => void
}) {
  return (
    <button
      aria-checked={active}
      className={`inline-flex h-8 items-center gap-1.5 rounded-full px-3 font-body-sm text-body-sm font-semibold transition-colors ${
        active
          ? 'bg-primary text-on-primary shadow-sm'
          : disabled
            ? 'cursor-not-allowed text-on-surface-variant/40'
            : 'text-on-surface-variant hover:bg-surface-container-high hover:text-primary'
      }`}
      disabled={disabled}
      role="radio"
      title={hint}
      type="button"
      onClick={onClick}
    >
      <MaterialIcon name={icon} className="text-[18px]" />
      <span className="hidden sm:inline">{label}</span>
    </button>
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
