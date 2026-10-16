import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from 'react'
import {
  Link,
  useLocation,
  useNavigate,
  useNavigationType,
  useParams,
} from 'react-router-dom'
import { ApiError } from '../api/client'
import { getInspectorRecord } from '../api/inspector'
import { clauseOrdinal } from '../api/clauseReview'
import {
  getContractGraphEvidence,
  type ContractGraphEdge,
  type ContractGraphKind,
} from '../api/contractGraph'
import {
  analysisState,
  contractDocument,
  getDossierStructure,
  listDocumentTables,
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
import { restartOcrErrorMessage, retryDossierFailed } from '../api/dossiers'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { useDossierPermissions } from '../auth/dossierPermissions'
import { AnalysisNotice } from '../components/AnalysisNotice'
import { CitationPane } from '../components/CitationPane'
import { ConflictNotice } from '../components/ConflictNotice'
import { UploadedPdfPane } from '../components/UploadedPdfPane'
import { CitedAnswer } from '../components/CitedAnswer'
import { SearchCitationReview } from '../components/SearchCitationReview'
import { StructureDocument } from '../components/StructureDocument'
import { StructureMindmap } from '../components/StructureMindmap'
import { StructureOutline } from '../components/StructureOutline'

import { Ai2GraphDossierView } from '../components/ai2-graph/ContractGraphCanvas'
import { ContentSharingConsent } from '../components/ai2-graph/ContentSharingConsent'
import {
  AI2_GRAPH_UI_ENABLED,
  createLatestRequestGuard,
  isLegacyCitationFallbackAllowed,
} from '../components/ai2-graph/contractGraphRuntime'
import { QueryHistoryPanel } from '../components/QueryHistoryPanel'
import { SearchAudit } from '../components/SearchAudit'
import { TableStructure } from '../components/TableStructure'
import { MaterialIcon } from '../components/icons'
import {
  useHeaderShowsPageTitle,
  usePageBreadcrumb,
  usePageTitle,
} from '../hooks/usePageTitle'
import { useAnalysisWatch } from '../hooks/useAnalysisWatch'
import { useCompactSidebar } from '../hooks/useSidebar'
import {
  buildStructureTree,
  inferStructureMode,
  parseStructureMode,
  parseStructureView,
  STRUCTURE_VIEW_KEY,
  structureModes,
  structureViews,
  type OcrLine,
  type StructureMode,
  type StructureView,
} from '../structure'
import { readingPrefs, useReadingPrefs } from '../structure/readingPrefs'

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function readFocusedCitation(value: unknown): {
  hit: DossierSearchResult['hits'][number]
  index: number
} | null {
  const state = asRecord(value)
  const row = asRecord(state?.focusCitation)
  const text = typeof row?.text === 'string' ? row.text.trim() : ''
  const pageNo = typeof row?.pageNo === 'number' ? row.pageNo : null
  if (!text || pageNo === null) return null
  const sourceFileId =
    typeof row.sourceFileId === 'string' ? row.sourceFileId : null
  const lineId = typeof row.lineId === 'string' ? row.lineId : null
  const bbox =
    Array.isArray(row.bbox) &&
    row.bbox.length === 4 &&
    row.bbox.every(
      (item): item is number =>
        typeof item === 'number' && Number.isFinite(item),
    )
      ? ([row.bbox[0], row.bbox[1], row.bbox[2], row.bbox[3]] as [
          number,
          number,
          number,
          number,
        ])
      : null
  const status = sourceFileId && lineId ? 'LOCATABLE' : 'PARTIAL'
  const index = typeof row.index === 'number' && row.index >= 0 ? row.index : 0
  return {
    index,
    hit: {
      text,
      pageNo,
      sourceFileId,
      lineId,
      bbox,
      citation: {
        status,
        sourceFileId,
        lineId,
        pageNo,
        bbox,
        nodeId: null,
        quote: text,
      },
    },
  }
}
import {
  citationTableBbox,
  citationNode,
  citationNumbers,
  findClause,
  findClauseByQuote,
  searchCites,
  type SearchCite,
} from '../structure/citations'
import {
  anchorConflicts,
  conflictMarkers,
  openConflictCount,
} from '../structure/conflictAnchors'
import { conflictPagePath } from '../data/dossiers'

type Phase = 'loading' | 'ocr' | 'ready' | 'failed' | 'error'

function stateStructureMode(state: unknown): StructureMode | null {
  if (!state || typeof state !== 'object') return null
  return parseStructureMode(
    (state as { structureMode?: unknown }).structureMode,
  )
}

/**
 * Kiểu xem khi mở trang: theo Cài đặt nếu đã chọn, không thì kiểu dùng lần
 * trước (nhớ theo trình duyệt); mặc định sơ đồ tư duy.
 */
function storedStructureView(): StructureView {
  const { openView } = readingPrefs()
  if (openView !== 'last') return openView
  try {
    return (
      parseStructureView(window.localStorage.getItem(STRUCTURE_VIEW_KEY)) ??
      'mindmap'
    )
  } catch {
    return 'mindmap'
  }
}

function stateQuery(state: unknown) {
  if (!state || typeof state !== 'object') return ''
  const query = (state as { query?: unknown }).query
  return typeof query === 'string' ? query : ''
}

/** Khung đang mở trên trang: hỏi đáp (qa) nằm dưới, thẩm định trích dẫn nằm trên. */
type StructurePanel = 'qa' | 'review' | null
const PANEL_DEPTH = { qa: 1, review: 2 } as const

function panelDepth(panel: StructurePanel) {
  return panel ? PANEL_DEPTH[panel] : 0
}

/**
 * Mỗi lần mở khung, trang ghi thêm một bước lịch sử (state.panel) để Back của
 * trình duyệt đóng khung thay vì rời trang. panelSteps là số bước đã ghi thêm.
 */
function statePanel(state: unknown): { panel: StructurePanel; steps: number } {
  const row = asRecord(state)
  const panel =
    row?.panel === 'qa' || row?.panel === 'review' ? row.panel : null
  const steps = typeof row?.panelSteps === 'number' ? row.panelSteps : 0
  return { panel, steps: panel ? steps : 0 }
}

function withPanel(state: unknown, panel: StructurePanel, steps: number) {
  // Bỏ query / focusCitation: chỉ dùng một lần khi vừa mở trang.
  const rest = { ...(asRecord(state) ?? {}) }
  delete rest.query
  delete rest.focusCitation
  return { ...rest, panel, panelSteps: steps }
}

export function DossierStructurePage() {
  const titleInHeader = useHeaderShowsPageTitle()
  const { dossierId = '' } = useParams()
  const permissions = useDossierPermissions(dossierId)
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const backTo = user ? dossiersPath(user.role) : '/'
  const backLabel = user ? dossiersLabel(user.role, user.backendRole) : 'Hồ sơ'
  const [attempt, setAttempt] = useState(0)
  const [phase, setPhase] = useState<Phase>('loading')
  const [detail, setDetail] = useState<DossierStructure | null>(null)
  const [filename, setFilename] = useState<string | null>(null)
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [citeId, setCiteId] = useState<string | null>(null)
  const [reviewCiteId, setReviewCiteId] = useState<string | null>(null)
  const [tableCite, setTableCite] = useState<{
    node: ClauseNode
    citeNo: number
  } | null>(null)
  // Dòng OCR thô: cây được dựng trên trình duyệt theo loại tài liệu.
  const [lines, setLines] = useState<OcrLine[] | null>(null)
  const [showLines, setShowLines] = useState(false)
  const [pdfDocumentId, setPdfDocumentId] = useState<string | null>(null)
  // Cây AI1 trả sẵn, chỉ dùng khi backend không trả được dòng OCR.
  const [fallbackNodes, setFallbackNodes] = useState<ClauseNode[]>([])
  const [mode, setMode] = useState<StructureMode | null>(
    stateStructureMode(location.state),
  )
  const [view, setView] = useState<StructureView>(storedStructureView)

  const [showAi2Graph, setShowAi2Graph] = useState(false)
  const [ai2GraphKind, setAi2GraphKind] = useState<ContractGraphKind>('pair')
  const [graphClauses, setGraphClauses] = useState<
    Record<string, ClauseNode[]>
  >({})
  const [graphLines, setGraphLines] = useState<
    Record<string, { id: string; pageNo: number; text: string }[]>
  >({})
  const [ai2Citation, setAi2Citation] = useState<Record<
    string,
    unknown
  > | null>(null)
  const [ai2CitationError, setAi2CitationError] = useState(false)
  const [ai2CitationLoading, setAi2CitationLoading] = useState(false)
  const ai2CitationRequests = useRef(createLatestRequestGuard())
  const prefs = useReadingPrefs()
  const [spots, setSpots] = useState<ReviewSpot[]>([])
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchResult, setSearchResult] = useState<DossierSearchResult | null>(
    null,
  )
  const [searchCite, setSearchCite] = useState<{
    node: ClauseNode
    citeNo: number
    documentId: string
  } | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  // Hỏi lúc AI2 chưa xong: báo đang phân tích thay vì gửi câu hỏi.
  const [searchNotice, setSearchNotice] = useState<string | null>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  // Tăng mỗi lần hỏi hoặc đóng câu trả lời: kết quả về muộn của lượt cũ bị bỏ.
  const searchRun = useRef(0)
  // Tăng sau mỗi câu hỏi (kể cả lỗi) để lịch sử bên dưới tải lại.
  const [historyRefresh, setHistoryRefresh] = useState(0)
  const [error, setError] = useState<string | null>(null)
  usePageTitle(detail?.name ?? 'Cấu trúc hợp đồng')
  usePageBreadcrumb([
    { label: backLabel, to: backTo },
    ...(detail?.name ? [{ label: detail.name }] : []),
    { label: 'Cấu trúc cây' },
  ])

  const activeMode: StructureMode = mode ?? 'numbered'
  const tableHighlight = useMemo(() => {
    const hit = searchResult?.hits.find((item) => item.citation.tableId)
    return hit?.citation.tableId
      ? { tableId: hit.citation.tableId, cellId: hit.citation.cellId ?? null }
      : null
  }, [searchResult])
  const nodes = useMemo(
    () => (lines ? buildStructureTree(lines, activeMode) : fallbackNodes),
    [lines, activeMode, fallbackNodes],
  )
  useEffect(() => {
    if (!showAi2Graph || !detail) return
    const controller = new AbortController()
    let cancelled = false
    void Promise.all(
      detail.documents.map(async (document) => {
        const [documentLines, clauses] = await Promise.allSettled([
          loadDocumentLines(document.id, controller.signal),
          listClauses(document.id, controller.signal),
        ])
        return [
          document.id,
          {
            lines:
              documentLines.status === 'fulfilled'
                ? documentLines.value.map(({ id, pageNo, text }) => ({
                    id,
                    pageNo,
                    text,
                  }))
                : [],
            clauses: clauses.status === 'fulfilled' ? clauses.value : [],
          },
        ] as const
      }),
    ).then((entries) => {
      if (!cancelled) {
        setGraphClauses(
          Object.fromEntries(entries.map(([id, value]) => [id, value.clauses])),
        )
        setGraphLines(
          Object.fromEntries(entries.map(([id, value]) => [id, value.lines])),
        )
      }
    })
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [detail, showAi2Graph])
  // Câu trả lời AI2 không đi theo loại cấu trúc đang xem.
  const answerNodes = useMemo(
    () => (lines ? buildStructureTree(lines, 'numbered') : fallbackNodes),
    [lines, fallbackNodes],
  )
  useEffect(() => {
    setQuery('')
    setSearchResult(null)
    setSearchCite(null)
    setSearchError(null)
    setSearchNotice(null)
    setReviewCiteId(null)
    setShowAi2Graph(false)
    setGraphClauses({})
    setGraphLines({})
    setAi2Citation(null)
    setAi2CitationError(false)
    setAi2CitationLoading(false)
    ai2CitationRequests.current.invalidate()
  }, [dossierId])
  // "Hỏi lại" từ trang lịch sử: điền sẵn câu hỏi, một lần cho mỗi bước lịch sử
  // (Back về bước đó không điền lại).
  const queryFilledKey = useRef<string | null>(null)
  useEffect(() => {
    const question = stateQuery(location.state)
    if (!question || queryFilledKey.current === location.key) return
    queryFilledKey.current = location.key
    setQuery(question)
    searchInputRef.current?.focus()
  }, [location.key, location.state])

  const answerOpen =
    searching ||
    Boolean(searchError) ||
    Boolean(searchNotice) ||
    Boolean(searchResult)
  // Bấm Lịch sử khi chưa hỏi: xem lịch sử hỏi đáp thay cho cấu trúc cây.
  const [historyOpen, setHistoryOpen] = useState(false)
  const qaMode = answerOpen || historyOpen

  // Back của trình duyệt đóng khung đang mở thay vì rời trang.
  const panel: StructurePanel = reviewCiteId ? 'review' : qaMode ? 'qa' : null
  const navigationType = useNavigationType()
  const panelSyncedKey = useRef<string | null>(null)
  useEffect(() => {
    const entry = statePanel(location.state)
    if (entry.panel === panel) {
      // Khung đã khớp bước lịch sử này: lần đổi khung sau là do người dùng bấm trên trang.
      panelSyncedKey.current = location.key
      return
    }
    const here = `${location.pathname}${location.search}${location.hash}`
    if (navigationType === 'POP' && panelSyncedKey.current !== location.key) {
      // Vừa Back/Forward: đưa khung về đúng bước lịch sử.
      panelSyncedKey.current = location.key
      if (panelDepth(entry.panel) < panelDepth(panel)) {
        if (entry.panel === null) closeAnswer()
        else setReviewCiteId(null)
      } else {
        // Forward tới khung đã đóng: không mở lại được, ghi đè bước này.
        navigate(here, {
          replace: true,
          state: withPanel(location.state, panel, entry.steps),
        })
      }
      return
    }
    if (panelDepth(panel) > panelDepth(entry.panel)) {
      navigate(here, {
        state: withPanel(location.state, panel, entry.steps + 1),
      })
    } else if (panel === null) {
      // Đóng bằng nút trên trang: bỏ các bước đã ghi thêm.
      navigate(-Math.max(1, entry.steps))
    } else if (entry.steps >= 2) {
      navigate(-1)
    } else {
      navigate(here, {
        replace: true,
        state: withPanel(location.state, panel, entry.steps),
      })
    }
  }, [location, navigate, navigationType, panel])

  async function submitSearch(event: FormEvent) {
    event.preventDefault()
    const question = query.trim()
    if (!dossierId || !question || searching) return
    if (ai2Locked) {
      remindAnalysis('Hỏi đáp')
      return
    }
    const run = ++searchRun.current
    setSearchNotice(null)
    setSearching(true)
    setSearchError(null)
    try {
      const result = await searchDossier(dossierId, question)
      if (run === searchRun.current) setSearchResult(result)
    } catch (cause: unknown) {
      if (run !== searchRun.current) return
      setSearchResult(null)
      setSearchError(
        structureErrorMessage(cause) ?? 'Không hỏi được hồ sơ này. Thử lại.',
      )
    } finally {
      if (run === searchRun.current) setSearching(false)
      setHistoryRefresh((current) => current + 1)
    }
  }

  /** Đóng riêng câu trả lời; phần lịch sử hỏi đáp vẫn mở. */
  function dismissAnswer() {
    searchRun.current += 1
    setSearching(false)
    setSearchResult(null)
    setSearchError(null)
    setSearchNotice(null)
    setSearchCite(null)
    setReviewCiteId(null)
    setHistoryOpen(true)
  }

  /** Đóng khung câu trả lời (về cấu trúc cây), kể cả khi câu hỏi còn đang chờ. */
  function closeAnswer() {
    searchRun.current += 1
    setSearching(false)
    setSearchResult(null)
    setSearchError(null)
    setSearchNotice(null)
    setSearchCite(null)
    setReviewCiteId(null)
    setHistoryOpen(false)
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
        // AI2 lỗi sau khi OCR xong: cây vẫn có, chỉ phần phân tích bị lỗi.
        const ai2Failed =
          analysisState(next.latestJobStatus, next.latestJobErrorCode) ===
          'failed'
        if (next.latestJobStatus === 'failed' && !ai2Failed) {
          setPhase('failed')
          return
        }
        if (!isOcrComplete(next.latestJobStatus) && !ai2Failed) {
          setPhase('ocr')
          timer = window.setTimeout(() => {
            void tick()
          }, 2000)
          return
        }
        const focusedCitation = readFocusedCitation(location.state)
        const document =
          (focusedCitation?.hit.sourceFileId
            ? next.documents.find(
                (candidate) =>
                  candidate.id === focusedCitation.hit.sourceFileId,
              )
            : null) ?? contractDocument(next)
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
          // Table-first contracts often have no Điều/Khoản markers. When the
          // upload did not persist a user-selected mode, infer the first view
          // from the actual OCR/table payload instead of forcing numbered.
          if (
            !next.structureMode &&
            stateStructureMode(location.state) === null
          ) {
            let hasTables = false
            if (buildStructureTree(ocrLines, 'numbered').length === 0) {
              try {
                hasTables =
                  (await listDocumentTables(document.id, controller.signal))
                    .length > 0
              } catch {
                hasTables = false
              }
            }
            if (stopped) return
            setMode(inferStructureMode(ocrLines, hasTables))
          }
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
        if (cause instanceof ApiError && cause.status === 403) {
          navigate(backTo, {
            replace: true,
            state: {
              notice:
                'Quyền xem hồ sơ này đã bị thu hồi. Chờ email chia sẻ mới để mở lại.',
              noticeTone: 'error',
            },
          })
          return
        }
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
  }, [attempt, backTo, dossierId, navigate])

  const analysis = detail
    ? analysisState(detail.latestJobStatus, detail.latestJobErrorCode)
    : null
  // Hỏi đáp, lịch sử hỏi đáp, xung đột và đồ thị dùng kết quả AI2: khoá tới khi
  // AI2 xong. Bấm vào thì banner nháy lên, nói rõ phần đó đang chờ.
  const ai2Locked = analysis === 'running' || analysis === 'failed'
  const [analysisNudge, setAnalysisNudge] = useState<{
    label: string
    at: number
  } | null>(null)
  function remindAnalysis(label: string) {
    setAnalysisNudge({ label, at: Date.now() })
  }
  const [retryingAnalysis, setRetryingAnalysis] = useState(false)
  const [retryAnalysisError, setRetryAnalysisError] = useState<string | null>(
    null,
  )
  async function retryAnalysis() {
    if (retryingAnalysis) return
    setRetryingAnalysis(true)
    setRetryAnalysisError(null)
    try {
      await retryDossierFailed(dossierId, 'ai2')
      setDetail(await getDossierStructure(dossierId))
      setAnalysisNudge(null)
    } catch (cause: unknown) {
      setRetryAnalysisError(
        restartOcrErrorMessage(cause) ?? 'Không chạy lại được phân tích.',
      )
    } finally {
      setRetryingAnalysis(false)
    }
  }
  // Cây đã xem được trong lúc AI2 chạy: AI2 xong thì tải lại xung đột.
  const [analysisJustFinished, setAnalysisJustFinished] = useState(false)
  const { percent: analysisPercent } = useAnalysisWatch(
    dossierId,
    phase === 'ready' && analysis === 'running',
    (next) => {
      setDetail(next)
      setSearchNotice(null)
      setAnalysisNudge(null)
      setAnalysisJustFinished(
        analysisState(next.latestJobStatus, next.latestJobErrorCode) === 'done',
      )
      listReviewSpots(dossierId)
        .then(setSpots)
        .catch(() => setSpots([]))
    },
  )

  // Xung đột neo bằng trang + dòng OCR bên hợp đồng → nút cây đang chứa dòng đó.
  const anchors = useMemo(
    () => anchorConflicts(spots, nodes, lines ?? [], documentId),
    [documentId, lines, nodes, spots],
  )
  const markers = useMemo(
    () => conflictMarkers(anchors, nodes),
    [anchors, nodes],
  )
  const answerAnchors = useMemo(
    () =>
      answerNodes === nodes
        ? anchors
        : anchorConflicts(spots, answerNodes, lines ?? [], documentId),
    [anchors, answerNodes, documentId, lines, nodes, spots],
  )
  const openConflicts = openConflictCount(spots)
  const openConflict = useCallback(
    (findingId: string) => {
      navigate(conflictPagePath(dossierId, findingId), {
        state: { dossierId, name: detail?.name, findingId },
      })
    },
    [detail?.name, dossierId, navigate],
  )
  const citeOf = useMemo(() => citationNumbers(nodes), [nodes])
  const answerCiteOf = useMemo(
    () => citationNumbers(answerNodes),
    [answerNodes],
  )
  const cited = citeId ? findClause(nodes, citeId) : null
  const pdfFile =
    detail?.documents.find((document) => document.id === pdfDocumentId) ?? null
  const splitView = Boolean(
    cited || tableCite || searchCite || showLines || pdfFile,
  )
  // Mở khung PDF / trích dẫn bên cạnh: thu gọn menu để nội dung không bị ép.
  useCompactSidebar(splitView)

  const openTreeCite = useCallback((id: string) => {
    setShowLines(false)
    setPdfDocumentId(null)
    setTableCite(null)
    setSearchCite(null)
    setCiteId(id)
  }, [])

  const resolveGraphEvidenceText = useCallback(
    (nodeId: string, sourceDocumentId?: string | null) => {
      const endpointDocumentId = sourceDocumentId ?? null
      if (!endpointDocumentId) return ''
      const line = (graphLines[endpointDocumentId] ?? []).find((item) => {
        const graphLineId = `line:${item.pageNo}:${item.id}`
        return nodeId === graphLineId || nodeId.startsWith(`${graphLineId}:`)
      })
      if (!line) return ''
      const clauseTree =
        endpointDocumentId === documentId
          ? nodes
          : (graphClauses[endpointDocumentId] ?? [])
      const clause = findClauseByQuote(clauseTree, line.text, line.pageNo)
      return (clause?.text || line.text).replace(/\s+/g, ' ').trim()
    },
    [documentId, graphClauses, graphLines, nodes],
  )

  const resolveGraphNodeLabel = useCallback(
    (nodeId: string, sourceDocumentId?: string | null) =>
      resolveGraphEvidenceText(nodeId, sourceDocumentId) ||
      'Không tải được nội dung điều khoản',
    [resolveGraphEvidenceText],
  )

  const resolveSelectedGraphEdgeEvidence = useCallback(
    async (edge: ContractGraphEdge) => {
      if (!detail?.ai2JobId || !detail.snapshotDigest) return null
      const endpoints = [
        {
          nodeId: edge.source_node_id,
          documentId: edge.source_document_id,
          citationRef: edge.source_citation_ref,
        },
        {
          nodeId: edge.target_node_id,
          documentId: edge.target_document_id,
          citationRef: edge.target_citation_ref,
        },
      ]
      const found = await Promise.all(
        endpoints.map(async (endpoint) => {
          if (
            !endpoint.documentId ||
            !detail.documents.some(
              (document) => document.id === endpoint.documentId,
            )
          )
            return null
          try {
            const evidence = endpoint.citationRef.startsWith('cite:')
              ? await getContractGraphEvidence({
                  dossierId,
                  jobId: detail.ai2JobId!,
                  snapshotDigest: detail.snapshotDigest!,
                  graphKind: ai2GraphKind,
                  nodeId: endpoint.nodeId,
                  citationRef: endpoint.citationRef,
                })
              : await getInspectorRecord('citation', endpoint.citationRef)
            return typeof evidence.quote === 'string' ? evidence.quote : null
          } catch {
            return null
          }
        }),
      )
      return {
        ...(found[0] ? { sourceText: found[0] } : {}),
        ...(found[1] ? { targetText: found[1] } : {}),
      }
    },
    [ai2GraphKind, detail, dossierId],
  )

  const clearAi2Citation = useCallback(() => {
    ai2CitationRequests.current.invalidate()
    setAi2Citation(null)
    setAi2CitationError(false)
    setAi2CitationLoading(false)
  }, [])

  const openAi2Citation = useCallback(
    async (
      citationRef: string,
      nodeId: string,
      sourceDocumentId?: string | null,
    ) => {
      const requestId = ai2CitationRequests.current.start()
      setAi2Citation(null)
      setAi2CitationError(false)
      setAi2CitationLoading(true)
      try {
        const record = citationRef.startsWith('cite:')
          ? await getContractGraphEvidence({
              dossierId,
              jobId: detail?.ai2JobId ?? '',
              snapshotDigest: detail?.snapshotDigest ?? '',
              graphKind: ai2GraphKind,
              nodeId,
              citationRef,
            })
          : await getInspectorRecord('citation', citationRef)
        if (ai2CitationRequests.current.isCurrent(requestId))
          setAi2Citation({
            ...record,
            __node_id: nodeId,
            __document_id: sourceDocumentId,
          })
      } catch (error) {
        if (!ai2CitationRequests.current.isCurrent(requestId)) return
        // A legacy opaque handle may not be a Backend citation ID; use the already-loaded OCR clause if it maps exactly.
        const responseStatus =
          error && typeof error === 'object' && 'status' in error
            ? error.status
            : null
        if (
          isLegacyCitationFallbackAllowed(
            citationRef,
            typeof responseStatus === 'number' ? responseStatus : null,
            sourceDocumentId,
            documentId,
          ) &&
          findClause(nodes, nodeId) &&
          citeOf.has(nodeId)
        ) {
          openTreeCite(nodeId)
          return
        }
        setAi2CitationError(true)
      } finally {
        if (ai2CitationRequests.current.isCurrent(requestId))
          setAi2CitationLoading(false)
      }
    },
    [
      ai2GraphKind,
      citeOf,
      detail?.ai2JobId,
      detail?.snapshotDigest,
      dossierId,
      documentId,
      nodes,
      openTreeCite,
    ],
  )

  function openUploadedPdf(id: string) {
    setShowLines(false)
    setCiteId(null)
    setSearchCite(null)
    setTableCite(null)
    setReviewCiteId(null)
    setPdfDocumentId(id)
  }

  const openSearchCitation = useCallback(
    (hit: DossierSearchResult['hits'][number], index: number) => {
      const clause = findClauseByQuote(nodes, hit.text, hit.pageNo)
      if (clause && citeOf.has(clause.id)) {
        openTreeCite(clause.id)
        return
      }
      if (!documentId || hit.pageNo === null) return
      const node: ClauseNode = {
        id: hit.lineId || `search-citation-${index}`,
        nodeType: 'line',
        label: 'Citation',
        number: null,
        title: null,
        text: hit.text,
        pageStart: hit.pageNo,
        pageEnd: hit.pageNo,
        confidence: null,
        regions: hit.bbox ? [{ pageNo: hit.pageNo, bbox: hit.bbox }] : [],
        children: [],
      }
      setShowLines(false)
      setPdfDocumentId(null)
      setCiteId(null)
      setTableCite(null)
      setSearchCite({ node, citeNo: index + 1, documentId })
    },
    [citeOf, documentId, nodes, openTreeCite],
  )

  const openForeignSearchCitation = useCallback((cite: SearchCite) => {
    const foreignDocumentId = cite.documentId
    if (!foreignDocumentId) return
    setReviewCiteId(null)
    setPdfDocumentId(null)
    setCiteId(null)
    setTableCite(null)
    const node = citationNode(cite)
    setSearchCite({ node, citeNo: cite.n, documentId: foreignDocumentId })

    // Một số dòng bảng hợp lệ nhưng AI2 không có bbox dòng. Lấy bbox của cả
    // dòng từ endpoint bảng để vẫn mở cùng CitationPane và khoanh đúng nguồn.
    if (node.regions.length > 0) return
    listDocumentTables(foreignDocumentId)
      .then((tables) => {
        const bbox = citationTableBbox(cite, tables)
        if (!bbox) return
        setSearchCite((current) => {
          if (
            !current ||
            current.documentId !== foreignDocumentId ||
            current.node.id !== node.id
          ) {
            return current
          }
          return {
            ...current,
            node: citationNode({ ...cite, bbox }),
          }
        })
      })
      .catch(() => {
        // CitationPane vẫn hiển thị trang nguồn nếu bảng không có geometry.
      })
  }, [])

  // Mở trích dẫn được chọn từ trang khác, một lần cho mỗi bước lịch sử.
  const focusOpenedKey = useRef<string | null>(null)
  useEffect(() => {
    if (phase !== 'ready' || !documentId || searchCite) return
    if (focusOpenedKey.current === location.key) return
    const focused = readFocusedCitation(location.state)
    if (!focused) return
    focusOpenedKey.current = location.key
    openSearchCitation(focused.hit, focused.index)
  }, [
    documentId,
    location.key,
    location.state,
    openSearchCitation,
    phase,
    searchCite,
  ])

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
            {/* Có header thì đường dẫn nằm trên header: Hồ sơ › abc › Cấu trúc cây */}
            {titleInHeader ? null : (
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
            )}
            {/* Có khung PDF / trích dẫn bên cạnh thì chỗ hẹp: xếp ô hỏi xuống dòng dưới. */}
            <div
              className={`flex flex-col gap-space-sm ${splitView ? '' : 'md:flex-row md:items-start md:justify-between'}`}
            >
              <div className="flex min-w-0 flex-1 flex-col gap-space-xs">
                {titleInHeader ? null : (
                  <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
                    {detail?.name ?? 'Cấu trúc hợp đồng'}
                  </h1>
                )}
                {/* Dòng đầu: loại cấu trúc · kiểu xem | PDF gốc · nguồn OCR */}
                <div className="flex flex-wrap items-center gap-x-space-sm gap-y-1 font-body-sm text-body-sm text-on-surface-variant">
                  {phase === 'ready' && !qaMode ? (
                    <>
                      <div
                        aria-label="Loại cấu trúc tài liệu"
                        className="inline-flex items-center gap-0.5 rounded-full bg-surface-container p-1"
                        role="radiogroup"
                      >
                        {structureModes.map((item) => (
                          <SegmentButton
                            key={item.value}
                            active={item.value === activeMode}
                            disabled={
                              item.value === 'tables' ? !documentId : !lines
                            }
                            icon={item.icon}
                            label={item.short}
                            onClick={() => changeMode(item.value)}
                          />
                        ))}
                      </div>
                      {activeMode !== 'tables' ? (
                        <div
                          aria-label="Kiểu xem cấu trúc"
                          className="inline-flex items-center gap-0.5 rounded-full bg-surface-container p-1"
                          role="radiogroup"
                        >
                          {structureViews.map((item) => (
                            <SegmentButton
                              key={item.value}
                              active={item.value === view}
                              icon={item.icon}
                              label={item.label}
                              onClick={() => changeView(item.value)}
                            />
                          ))}
                        </div>
                      ) : null}
                      <span
                        aria-hidden
                        className="mx-space-xs h-6 w-px bg-outline-variant/40"
                      />
                    </>
                  ) : null}
                  {phase === 'ready' && documentId ? (
                    <button
                      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 font-label-sm text-label-sm font-semibold ${
                        pdfFile
                          ? 'bg-brand-100 text-brand-700 ring-1 ring-brand-200'
                          : 'bg-surface-container text-primary hover:bg-primary/10'
                      }`}
                      title={filename || undefined}
                      type="button"
                      onClick={() =>
                        pdfFile
                          ? setPdfDocumentId(null)
                          : openUploadedPdf(documentId)
                      }
                    >
                      <MaterialIcon
                        name="picture_as_pdf"
                        className="text-[14px]"
                      />
                      PDF gốc
                    </button>
                  ) : (
                    <span>
                      {activeMode === 'tables'
                        ? 'Các bảng đã trích từ hợp đồng.'
                        : 'Hệ thống đọc hợp đồng rồi dựng cây điều khoản.'}
                    </span>
                  )}
                  {phase === 'ready' ? (
                    <>
                      <MetaDot />
                      {lines ? (
                        <button
                          aria-expanded={showLines}
                          className={`inline-flex items-center gap-1 whitespace-nowrap underline-offset-2 transition-colors hover:text-primary hover:underline ${
                            showLines ? 'text-primary' : ''
                          }`}
                          title="Xem các dòng chữ đang dùng để dựng cây"
                          type="button"
                          onClick={() => {
                            setCiteId(null)
                            setShowLines((open) => !open)
                          }}
                        >
                          {lines.length} dòng chữ
                          <MaterialIcon
                            name={showLines ? 'close' : 'open_in_new'}
                            style={{ fontSize: 14 }}
                          />
                        </button>
                      ) : (
                        <span title="Chưa có từng dòng chữ của tài liệu">
                          cấu trúc dựng sẵn
                        </span>
                      )}
                    </>
                  ) : null}
                  {/* Số xung đột chờ xử lý đã hiện trên biểu tượng xung đột. */}
                  {detail?.hasConflicts && detail.pendingConflicts === 0 ? (
                    <span className="inline-flex items-center rounded bg-amber-50 px-space-xs py-0.5 font-label-sm text-label-sm font-semibold text-amber-900">
                      Có xung đột đã xử lý
                    </span>
                  ) : null}
                </div>
              </div>
              {phase === 'ready' ? (
                <div className="flex w-full shrink-0 items-center gap-space-sm pr-2 pt-1.5 md:w-auto">
                  {AI2_GRAPH_UI_ENABLED ? (
                    <button
                      aria-disabled={ai2Locked || undefined}
                      aria-pressed={showAi2Graph}
                      className={`relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border shadow-[0_1px_2px_rgba(15,23,42,0.06)] ${showAi2Graph ? 'border-primary bg-primary text-white' : 'border-outline-variant/30 bg-surface-container-lowest text-on-surface hover:bg-surface-container'} ${ai2Locked ? 'opacity-50' : ''}`}
                      title={
                        ai2Locked ? 'Graph AI2 · đang phân tích' : 'Graph AI2'
                      }
                      type="button"
                      onClick={() =>
                        ai2Locked
                          ? remindAnalysis('Đồ thị quan hệ')
                          : setShowAi2Graph((shown) => !shown)
                      }
                    >
                      <MaterialIcon name="hub" className="text-[18px]" />
                      {ai2Locked ? <LockBadge /> : null}
                      <span className="sr-only">Graph AI2</span>
                    </button>
                  ) : null}
                  <form
                    className="relative min-w-0 w-full shrink md:w-80 lg:w-96"
                    onSubmit={(event) => void submitSearch(event)}
                  >
                    <MaterialIcon
                      name="search"
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-outline"
                    />
                    <input
                      aria-disabled={ai2Locked || undefined}
                      aria-label="Hỏi về hợp đồng"
                      className={`h-10 w-full rounded-full border border-outline-variant/30 bg-surface-container-lowest pl-9 pr-space-md font-body-sm text-body-sm text-on-surface shadow-[0_1px_2px_rgba(15,23,42,0.06)] placeholder:text-outline focus:outline-none focus:ring-1 focus:ring-secondary ${
                        ai2Locked ? 'cursor-not-allowed opacity-60' : ''
                      }`}
                      placeholder={
                        ai2Locked
                          ? 'Hỏi đáp mở khi phân tích xong'
                          : 'Hỏi về hợp đồng này…'
                      }
                      readOnly={ai2Locked}
                      type="search"
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      onClick={
                        ai2Locked ? () => remindAnalysis('Hỏi đáp') : undefined
                      }
                    />
                    {ai2Locked ? (
                      <MaterialIcon
                        name="lock"
                        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[16px] text-outline"
                      />
                    ) : null}
                  </form>

                  {/* Đang hỏi đáp: về cấu trúc cây. Đang ở cấu trúc cây: mở lịch sử hỏi đáp. */}
                  <button
                    aria-disabled={(!qaMode && ai2Locked) || undefined}
                    className={`relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-outline-variant/30 bg-surface-container-lowest text-on-surface shadow-[0_1px_2px_rgba(15,23,42,0.06)] hover:bg-surface-container ${
                      !qaMode && ai2Locked ? 'opacity-50' : ''
                    }`}
                    title={
                      qaMode
                        ? 'Cấu trúc cây'
                        : ai2Locked
                          ? 'Lịch sử hỏi đáp · đang phân tích'
                          : 'Lịch sử hỏi đáp'
                    }
                    type="button"
                    onClick={
                      qaMode
                        ? closeAnswer
                        : ai2Locked
                          ? () => remindAnalysis('Lịch sử hỏi đáp')
                          : () => setHistoryOpen(true)
                    }
                  >
                    <MaterialIcon
                      name={qaMode ? 'account_tree' : 'history'}
                      className="text-[18px]"
                    />
                    {!qaMode && ai2Locked ? <LockBadge /> : null}
                    <span className="sr-only">
                      {qaMode ? 'Cấu trúc cây' : 'Lịch sử hỏi đáp'}
                    </span>
                  </button>
                  {ai2Locked ? (
                    <button
                      aria-disabled
                      className="relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-outline-variant/30 bg-surface-container-lowest text-on-surface opacity-50 shadow-[0_1px_2px_rgba(15,23,42,0.06)]"
                      title="Xem xung đột · đang phân tích"
                      type="button"
                      onClick={() => remindAnalysis('Xung đột')}
                    >
                      <MaterialIcon
                        name="warning"
                        className="text-[18px] text-amber-700"
                      />
                      <LockBadge />
                      <span className="sr-only">Xem xung đột</span>
                    </button>
                  ) : (
                    <Link
                      className="relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-outline-variant/30 bg-surface-container-lowest text-on-surface shadow-[0_1px_2px_rgba(15,23,42,0.06)] hover:bg-amber-50"
                      state={{ dossierId, name: detail?.name }}
                      title={
                        openConflicts > 0
                          ? `Xem xung đột · ${openConflicts} chưa ai thẩm định`
                          : 'Xem xung đột'
                      }
                      to={conflictPagePath(dossierId)}
                    >
                      <MaterialIcon
                        name="warning"
                        className="text-[18px] text-amber-700"
                      />
                      <span className="sr-only">Xem xung đột</span>
                      {openConflicts > 0 ? (
                        <span className="absolute -right-1.5 -top-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-400 px-1 font-label-sm text-[10px] font-bold text-amber-950">
                          {openConflicts}
                        </span>
                      ) : null}
                    </Link>
                  )}
                </div>
              ) : null}
            </div>
          </div>

          {phase === 'ready' ? (
            <AnalysisNotice
              className="mb-space-md shrink-0"
              errorCode={detail?.latestJobErrorCode}
              justFinished={analysisJustFinished}
              nudge={analysisNudge}
              percent={analysisPercent}
              retrying={retryingAnalysis}
              state={analysis}
              waitingFor="Hỏi đáp, lịch sử hỏi đáp, xung đột và đồ thị quan hệ"
              onDismiss={() => setAnalysisJustFinished(false)}
              onRetry={
                permissions.canEdit ? () => void retryAnalysis() : undefined
              }
            />
          ) : null}
          {phase === 'ready' && retryAnalysisError ? (
            <p
              className="mb-space-md shrink-0 rounded-lg bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container"
              role="alert"
            >
              {retryAnalysisError}
            </p>
          ) : null}

          {phase === 'loading' || phase === 'ocr' ? (
            <section className="bg-surface-container-lowest p-space-xl rounded-xl shadow-sm flex items-start gap-space-md">
              <MaterialIcon
                name="progress_activity"
                className="text-primary text-[22px] animate-spin"
              />
              <div className="flex flex-col gap-space-xs">
                {phase === 'ocr' ? (
                  <>
                    <h2 className="font-title-sm text-title-sm text-primary">
                      Đang đọc tài liệu và dựng cấu trúc
                    </h2>
                    <p className="font-body-sm text-body-sm text-on-surface-variant">
                      Trang này tự cập nhật. Cấu trúc sẽ hiện khi đọc xong tài
                      liệu.
                    </p>
                  </>
                ) : (
                  <h2 className="font-title-sm text-title-sm text-primary">
                    Đang tải cấu trúc hợp đồng
                  </h2>
                )}
              </div>
            </section>
          ) : null}

          {phase === 'failed' ? (
            <section
              className="bg-error-container text-on-error-container p-space-xl rounded-xl"
              role="alert"
            >
              <h2 className="font-title-sm text-title-sm">
                Đọc tài liệu không hoàn tất
              </h2>
              <p className="font-body-sm text-body-sm mt-space-xs">
                Hồ sơ đã nhận tệp nhưng đọc tài liệu bị lỗi. Vui lòng thử lại
                hoặc báo quản trị viên.
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
                className="h-10 px-space-lg bg-brand-100 text-brand-700 hover:bg-brand-200 rounded-lg font-body-sm text-body-sm font-semibold"
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

          {phase === 'ready' && answerOpen ? (
            <section className="mb-space-md rounded-xl bg-surface-container-lowest px-space-md py-space-md shadow-sm">
              <div className="mb-space-sm flex items-center justify-between gap-space-sm">
                <p className="flex min-w-0 flex-wrap items-baseline gap-x-space-sm">
                  <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wide text-on-surface-variant">
                    Câu trả lời tổng hợp AI
                  </span>
                  <span className="font-body-sm text-body-sm text-outline">
                    AI có thể mắc lỗi. Hãy đối chiếu với điều khoản gốc trước
                    khi dùng.
                  </span>
                </p>
                <button
                  aria-label="Đóng câu trả lời"
                  className="-my-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface"
                  title="Đóng câu trả lời"
                  type="button"
                  onClick={dismissAnswer}
                >
                  <MaterialIcon name="close" className="text-[20px]" />
                </button>
              </div>
              {searching ? (
                <p
                  className="flex items-center gap-space-sm text-on-surface-variant"
                  role="status"
                >
                  <MaterialIcon
                    name="progress_activity"
                    className="animate-spin text-[18px] text-primary"
                  />
                  <span aria-hidden className="flex gap-1">
                    {[0, 150, 300].map((delay) => (
                      <span
                        key={delay}
                        className="h-1.5 w-1.5 animate-bounce rounded-full bg-on-surface-variant"
                        style={{ animationDelay: `${delay}ms` }}
                      />
                    ))}
                  </span>
                  <span className="sr-only">Đang tìm câu trả lời</span>
                </p>
              ) : null}
              {searchError ? (
                <p className="font-body-sm text-body-sm text-on-error-container">
                  {searchError}
                </p>
              ) : null}
              {searchNotice ? (
                <p
                  className="flex items-center gap-space-sm font-body-sm text-body-sm text-on-surface-variant"
                  role="status"
                >
                  <MaterialIcon
                    name="progress_activity"
                    className="animate-spin text-[18px] text-primary"
                  />
                  {searchNotice}
                </p>
              ) : null}
              {searchResult ? (
                <div className="flex flex-col gap-space-sm">
                  <SearchAudit result={searchResult} />
                  {searchResult.answer ? (
                    <CitedAnswer
                      activeId={reviewCiteId}
                      answer={searchResult.answer}
                      citationOf={answerCiteOf}
                      documentId={documentId}
                      hits={searchResult.hits}
                      nodes={answerNodes}
                      onCite={(cite) => {
                        if (cite.documentId && cite.documentId !== documentId) {
                          openForeignSearchCitation(cite)
                          return
                        }
                        setReviewCiteId(cite.id)
                      }}
                    />
                  ) : (
                    <p className="font-body-sm text-body-sm text-on-surface">
                      {searchResult.connected
                        ? 'AI chưa tìm được câu trả lời cho câu hỏi này.'
                        : 'AI đang bận hoặc phản hồi quá lâu nên chưa trả lời được. Thử hỏi lại sau ít phút.'}
                    </p>
                  )}
                  {searchCites(
                    answerNodes,
                    searchResult.hits,
                    answerCiteOf,
                    searchResult.answer ?? '',
                    documentId,
                  ).length === 0 && searchResult.hits.length > 0 ? (
                    <ul className="flex flex-col gap-1">
                      {searchResult.hits
                        .filter((hit) => {
                          const clause = findClauseByQuote(
                            nodes,
                            hit.text,
                            hit.pageNo,
                          )
                          return !clause || !citeOf.has(clause.id)
                        })
                        .map((hit, index) => (
                          <li
                            key={`${hit.lineId ?? ''}-${hit.pageNo ?? ''}-${hit.text}`}
                            className="font-body-sm text-body-sm text-on-surface-variant"
                          >
                            {hit.sourceFileId === documentId && hit.pageNo ? (
                              <button
                                className="group flex w-full items-start gap-2 rounded-md p-1 text-left hover:bg-primary/5 hover:text-primary"
                                type="button"
                                onClick={() => openSearchCitation(hit, index)}
                                title="Mở trang nguồn"
                              >
                                <span className="shrink-0 font-medium">
                                  Trang {hit.pageNo} ·
                                </span>
                                <span className="min-w-0 flex-1">
                                  {hit.text}
                                </span>
                                <MaterialIcon
                                  name="open_in_new"
                                  className="shrink-0 text-[15px] opacity-60 group-hover:opacity-100"
                                />
                              </button>
                            ) : (
                              <span>
                                {hit.pageNo ? `Trang ${hit.pageNo} · ` : ''}
                                {hit.text}
                              </span>
                            )}
                          </li>
                        ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </section>
          ) : null}

          {/* Đang xem câu trả lời: bên dưới là lịch sử hỏi đáp, cấu trúc cây ẩn tới khi bấm nút Cấu trúc cây */}
          {phase === 'ready' && qaMode && !reviewCiteId ? (
            <QueryHistoryPanel
              dossierId={dossierId}
              refreshKey={historyRefresh}
              onClose={closeAnswer}
              onReuse={(question) => {
                setQuery(question)
                searchInputRef.current?.focus()
              }}
              onCite={(citation, citeNo) => {
                const cite: SearchCite = {
                  id: citation.lineId ?? `history-citation-${citeNo}`,
                  n: citeNo,
                  quote: citation.quote,
                  documentId: citation.documentId,
                  pageNo: citation.pageNo,
                  lineId: citation.lineId,
                  bbox: citation.bbox,
                }
                // Trích dẫn ở phụ lục (tài liệu khác): mở đúng tài liệu đó như câu
                // trả lời trực tiếp, không dò trên cây của hợp đồng chính.
                if (citation.documentId && citation.documentId !== documentId) {
                  openForeignSearchCitation(cite)
                  return
                }
                if (!documentId) return
                const node = findClauseByQuote(
                  answerNodes,
                  citation.quote,
                  citation.pageNo,
                )
                if (!node) {
                  // Không khớp được nút cây: vẫn mở theo trang/vùng AI2 trả về.
                  if (citation.pageNo) {
                    openForeignSearchCitation({ ...cite, documentId })
                  }
                  return
                }
                setShowLines(false)
                setPdfDocumentId(null)
                setCiteId(null)
                setTableCite(null)
                setSearchCite({ node, citeNo, documentId })
              }}
            />
          ) : null}

          {phase === 'ready' &&
          !qaMode &&
          activeMode === 'tables' &&
          documentId ? (
            <TableStructure
              activeId={tableCite?.node.id}
              documentId={documentId}
              highlight={tableHighlight}
              query=""
              onCite={(node, citeNo) => {
                setShowLines(false)
                setCiteId(null)
                setTableCite({ node, citeNo })
              }}
            />
          ) : null}

          {phase === 'ready' &&
          reviewCiteId &&
          documentId &&
          findClause(answerNodes, reviewCiteId) ? (
            <SearchCitationReview
              citeNo={answerCiteOf.get(reviewCiteId) ?? 0}
              conflicts={answerAnchors.get(reviewCiteId)}
              documentId={documentId}
              dossierId={dossierId}
              filename={filename}
              node={findClause(answerNodes, reviewCiteId)!}
              ordinal={clauseOrdinal(answerNodes, reviewCiteId)}
              onOpenConflict={openConflict}
              reviewBlocked={permissions.reviewBlocked}
              onBack={() => setReviewCiteId(null)}
            />
          ) : null}

          {/* Thanh loại sơ đồ + quyền AI chỉ đi kèm phần đồ thị: cùng điều kiện hiện với nó. */}
          {phase === 'ready' &&
          showAi2Graph &&
          detail &&
          !qaMode &&
          !reviewCiteId ? (
            <div className="mb-space-md flex flex-wrap items-center justify-between gap-space-sm rounded-lg bg-surface-container-lowest px-space-lg py-space-sm shadow-sm">
              {/* Cùng kiểu nhóm nút chọn loại cấu trúc / kiểu xem ở thanh trên. */}
              <div
                className="inline-flex items-center gap-0.5 rounded-full bg-surface-container p-1"
                role="group"
                aria-label="Loại sơ đồ"
              >
                {(['pair', 'operation'] as const).map((kind) => (
                  <button
                    key={kind}
                    aria-pressed={ai2GraphKind === kind}
                    className={`inline-flex h-8 items-center gap-space-xs rounded-full px-space-md font-body-sm text-body-sm font-semibold transition-colors ${
                      ai2GraphKind === kind
                        ? 'bg-brand-100 text-brand-700 shadow-sm ring-1 ring-brand-200'
                        : 'text-on-surface-variant hover:bg-surface-container-high hover:text-primary'
                    }`}
                    type="button"
                    onClick={() => setAi2GraphKind(kind)}
                  >
                    <MaterialIcon
                      name={kind === 'pair' ? 'link' : 'edit_note'}
                      className="text-[18px]"
                    />
                    {kind === 'pair'
                      ? 'Quan hệ điều khoản'
                      : 'Sửa đổi điều khoản'}
                  </button>
                ))}
              </div>
              <ContentSharingConsent
                dossierId={dossierId}
                enabled={detail.metadata?.ai2_content_sharing_consent === true}
                canChange={permissions.known && permissions.canManage}
                onSaved={(enabled) =>
                  setDetail((current) =>
                    current
                      ? {
                          ...current,
                          metadata: {
                            ...(current.metadata ?? {}),
                            ai2_content_sharing_consent: enabled,
                          },
                        }
                      : current,
                  )
                }
              />
            </div>
          ) : null}

          {phase === 'ready' &&
          !qaMode &&
          !reviewCiteId &&
          (activeMode !== 'tables' || showAi2Graph) ? (
            <div className="flex min-h-[520px] flex-1 flex-col pb-space-md">
              {showAi2Graph ? (
                detail?.ai2JobId && detail.snapshotDigest ? (
                  <Ai2GraphDossierView
                    key={`${detail.ai2JobId}:${detail.snapshotDigest}:${ai2GraphKind}`}
                    enabled={AI2_GRAPH_UI_ENABLED}
                    dossierId={dossierId}
                    jobId={detail.ai2JobId}
                    snapshotDigest={detail.snapshotDigest}
                    graphKind={ai2GraphKind}
                    resolveNodeLabel={resolveGraphNodeLabel}
                    onOpenCitation={openAi2Citation}
                    onSelectRelation={clearAi2Citation}
                    onResolveEdgeEvidence={resolveSelectedGraphEdgeEvidence}
                    citationRecord={ai2Citation}
                    citationError={ai2CitationError}
                    citationLoading={ai2CitationLoading}
                  />
                ) : (
                  <p
                    role="status"
                    className="rounded-lg bg-surface-container-lowest p-space-lg font-body-sm text-body-sm text-on-surface-variant shadow-sm"
                  >
                    {analysis === 'running'
                      ? 'Đang phân tích hồ sơ. Sơ đồ quan hệ sẽ hiện khi phân tích xong.'
                      : 'Chưa có dữ liệu để vẽ sơ đồ quan hệ cho hồ sơ này.'}
                  </p>
                )
              ) : activeMode !== 'tables' ? (
                (() => {
                  const shared = {
                    markers: prefs.highlightConflicts ? markers : undefined,
                    citationOf: citeOf,
                    focusId: citeId,
                    autoScroll: prefs.autoScroll,
                    nodes,
                    title: detail?.name ?? 'Hợp đồng',
                    onCite: openTreeCite,
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
                        />
                      )
                    default:
                      // key để đổi hướng thì dựng lại, tự căn vừa khung.
                      return <StructureMindmap key="mindmap" {...shared} />
                  }
                })()
              ) : null}
            </div>
          ) : null}
        </div>
        {pdfFile ? (
          <UploadedPdfPane
            documentId={pdfFile.id}
            filename={pdfFile.filename}
            files={detail?.documents ?? []}
            onClose={() => setPdfDocumentId(null)}
            onSelect={openUploadedPdf}
          />
        ) : null}
        {showLines && lines ? (
          <OcrLinesPane lines={lines} onClose={() => setShowLines(false)} />
        ) : null}
        {searchCite && documentId ? (
          <CitationPane
            key={searchCite.node.id}
            citeNo={searchCite.citeNo}
            documentId={searchCite.documentId}
            filename={
              detail?.documents.find(
                (document) => document.id === searchCite.documentId,
              )?.filename ?? filename
            }
            node={searchCite.node}
            onClose={() => setSearchCite(null)}
          />
        ) : cited && documentId ? (
          <CitationPane
            key={cited.id}
            banner={
              anchors.get(cited.id)?.length ? (
                <ConflictNotice
                  documentId={documentId}
                  dossierId={dossierId}
                  nodeId={cited.id}
                  spots={anchors.get(cited.id) ?? []}
                  onOpen={openConflict}
                />
              ) : null
            }
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

/** Ổ khoá nhỏ ở góc nút: phần này chờ phân tích xong. */
function LockBadge() {
  return (
    <span
      aria-hidden
      className="absolute -right-1 -top-1 inline-flex h-4 w-4 items-center justify-center rounded-full bg-surface-container-lowest text-on-surface-variant ring-1 ring-outline-variant/40"
    >
      <MaterialIcon name="lock" style={{ fontSize: 11 }} />
    </span>
  )
}

function SegmentButton({
  active,
  disabled,
  icon,
  label,
  onClick,
}: {
  active: boolean
  disabled?: boolean
  icon: string
  label: string
  onClick: () => void
}) {
  return (
    <button
      aria-checked={active}
      className={`inline-flex h-8 w-10 items-center justify-center rounded-full font-body-sm text-body-sm font-semibold transition-colors ${
        active
          ? 'bg-brand-100 text-brand-700 ring-1 ring-brand-200 shadow-sm'
          : disabled
            ? 'cursor-not-allowed text-on-surface-variant/40'
            : 'text-on-surface-variant hover:bg-surface-container-high hover:text-primary'
      }`}
      disabled={disabled}
      role="radio"
      // Chỉ hiện icon; di chuột vào thì hiện tên.
      title={label}
      type="button"
      onClick={onClick}
    >
      <MaterialIcon name={icon} className="text-[18px]" />
      <span className="sr-only">{label}</span>
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
            {lines.length} dòng chữ
          </p>
          <p className="font-label-sm text-label-sm text-on-surface-variant">
            Đúng các dòng đang dùng để dựng cây, đủ chữ.
          </p>
        </div>
        <button
          aria-label="Đóng danh sách dòng chữ"
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
