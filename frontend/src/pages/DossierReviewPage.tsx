import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  getDossierStructure,
  searchDossier,
  structureErrorMessage,
  type DossierSearchResult,
  type DossierStructure,
} from '../api/structure'
import { DossierStructurePreview } from '../components/DossierStructurePreview'
import { DossierAuditLog } from '../components/DossierAuditLog'
import { DossierSearchResults } from '../components/DossierSearchResults'
import {
  ContextFindingsPanel,
  type ContextFindingsPanelModel,
} from '../components/ContextFindingsPanel'
import {
  DynamicCitationViewer,
  type CitationViewerModel,
} from '../components/DynamicCitationViewer'
import {
  FindingQueue,
  type FindingQueueEntry,
} from '../components/FindingQueue'
import { MaterialIcon } from '../components/icons'
import { auditTotalCount, exportAuditCsv } from '../data/auditLog'
import { usePageTitle } from '../hooks/usePageTitle'
import {
  approveDossier,
  listReviewItems,
  listReviewRevisions,
  lockDossier,
  ReviewConflictError,
  submitReviewAction,
  type ReviewActionType,
  type ReviewItem,
  type ReviewRevision,
} from '../api/review'
import {
  listDossierFacts,
  listDossierFindings,
  type DossierFact,
  type DossierFinding,
  type StructuredEvidence,
} from '../api/analysis'
import type { Ai2SearchHit } from '../api/ai2'

type ReviewTab = 'search' | 'activity' | 'clauses' | 'risk'
type ExportState = 'idle' | 'saving' | 'done'

const tabs: Array<{
  id: ReviewTab
  icon: string
  label: string
  badge?: string
}> = [
  { id: 'search', icon: 'document_scanner', label: 'Tìm kiếm & Rà soát' },
  {
    id: 'activity',
    icon: 'history_edu',
    label: 'Nhật ký hoạt động',
    badge: auditTotalCount + ' sự kiện',
  },
  { id: 'clauses', icon: 'gavel', label: 'Đối chiếu Điều khoản' },
  { id: 'risk', icon: 'shield_with_heart', label: 'Đánh giá Rủi ro' },
]

function csvCell(value: unknown) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}

function exportDossierEvidence(
  dossierId: string,
  result: DossierSearchResult | null,
  reviewItems: ReviewItem[],
) {
  const header = [
    'dossier_id',
    'query',
    'answer',
    'review_state',
    'source_file_id',
    'line_id',
    'page',
    'bbox',
    'citation_status',
    'quote',
    'open_review_items',
  ].join(',')
  const hits = result?.hits ?? []
  const rows = (hits.length > 0 ? hits : [null]).map((hit) =>
    [
      dossierId,
      result?.query,
      result?.answer,
      result?.reviewState ?? 'NEEDS_REVIEW',
      hit?.citation.sourceFileId,
      hit?.citation.lineId,
      hit?.citation.pageNo ?? hit?.pageNo,
      hit?.citation.bbox ? JSON.stringify(hit.citation.bbox) : '',
      hit?.citation.status,
      hit?.citation.quote || hit?.text,
      reviewItems.length,
    ]
      .map(csvCell)
      .join(','),
  )
  const blob = new Blob([`${header}\n${rows.join('\n')}`], {
    type: 'text/csv;charset=utf-8;',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `dossier-${dossierId}-evidence.csv`
  link.click()
  URL.revokeObjectURL(url)
}

export function DossierReviewPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const params = useParams<{ dossierId?: string }>()
  const state = location.state as {
    dossierId?: string
    name?: string
    showSearch?: boolean
    tab?: ReviewTab
  } | null
  const dossierId =
    params.dossierId ||
    state?.dossierId ||
    new URLSearchParams(location.search).get('dossierId') ||
    ''
  const [tab, setTab] = useState<ReviewTab>(
    location.pathname === '/nhat-ky-phap-ly'
      ? 'activity'
      : (state?.tab ?? 'search'),
  )
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchResult, setSearchResult] = useState<DossierSearchResult | null>(
    null,
  )
  const [selectedCitation, setSelectedCitation] = useState<Ai2SearchHit | null>(
    null,
  )
  const [searchError, setSearchError] = useState<string | null>(null)
  const [detail, setDetail] = useState<DossierStructure | null>(null)
  const [exportState, setExportState] = useState<ExportState>('idle')
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([])
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [reviewActionItemId, setReviewActionItemId] = useState<string | null>(
    null,
  )
  const [reviewMessage, setReviewMessage] = useState<string | null>(null)
  const [selectedReviewItemId, setSelectedReviewItemId] = useState<
    string | null
  >(null)
  const [revisions, setRevisions] = useState<ReviewRevision[]>([])
  const [revisionLoading, setRevisionLoading] = useState(false)
  const [correctionDrafts, setCorrectionDrafts] = useState<
    Record<string, string>
  >({})
  const [lifecycleBusy, setLifecycleBusy] = useState(false)
  const [facts, setFacts] = useState<DossierFact[]>([])
  const [findings, setFindings] = useState<DossierFinding[]>([])
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  const findingQueueEntries = useMemo<FindingQueueEntry[]>(
    () =>
      reviewItems.map((item) => {
        const snapshot = item.targetSnapshot ?? {}
        const leftEvidence =
          typeof snapshot.left_evidence === 'string'
            ? snapshot.left_evidence
            : typeof snapshot.leftEvidence === 'string'
              ? snapshot.leftEvidence
              : ''
        const rightEvidence =
          typeof snapshot.right_evidence === 'string'
            ? snapshot.right_evidence
            : typeof snapshot.rightEvidence === 'string'
              ? snapshot.rightEvidence
              : ''
        return {
          item,
          severity:
            typeof snapshot.severity === 'string'
              ? snapshot.severity
              : item.priority,
          topic:
            typeof snapshot.topic === 'string'
              ? snapshot.topic
              : `${item.targetType}/${item.targetId}`,
          leftEvidence,
          rightEvidence,
          revisions: selectedReviewItemId === item.id ? revisions : [],
        }
      }),
    [revisions, reviewItems, selectedReviewItemId],
  )

  const contextPanelModel = useMemo<ContextFindingsPanelModel | null>(() => {
    if (!searchResult) return null
    const contextFindings = (searchResult.contextFindings ?? []).flatMap(
      (value, index) => {
        if (!value || typeof value !== 'object' || Array.isArray(value))
          return []
        const row = value as Record<string, unknown>
        return [
          {
            id:
              typeof row.finding_id === 'string'
                ? row.finding_id
                : `context-${index}`,
            reasonCode:
              typeof row.reason_code === 'string'
                ? row.reason_code
                : typeof row.reason === 'string'
                  ? row.reason
                  : 'CONTEXT_FINDING',
            subject:
              typeof row.subject_key === 'string'
                ? row.subject_key
                : 'Context finding',
            reviewState:
              typeof row.review_state === 'string'
                ? row.review_state
                : 'NEEDS_REVIEW',
          },
        ]
      },
    )
    const evidenceIssues = (searchResult.evidenceIssues ?? []).flatMap(
      (value, index) => {
        if (!value || typeof value !== 'object' || Array.isArray(value))
          return []
        const row = value as Record<string, unknown>
        return [
          {
            code:
              typeof row.code === 'string'
                ? row.code
                : `EVIDENCE_ISSUE_${index + 1}`,
            message:
              typeof row.message === 'string'
                ? row.message
                : typeof row.reason === 'string'
                  ? row.reason
                  : 'Backend đánh dấu evidence cần rà soát.',
          },
        ]
      },
    )
    const trace = (searchResult.reasoningTrace ?? []).flatMap((value) =>
      value && typeof value === 'object' && !Array.isArray(value)
        ? [value as Record<string, unknown>]
        : [],
    )
    return {
      facts: searchResult.facts ?? [],
      findings: searchResult.findings ?? [],
      contextFindings,
      evidenceIssues,
      coverage: searchResult.coverage ?? {},
      trace,
      reviewState: searchResult.reviewState,
    }
  }, [searchResult])

  const viewerCitation = useMemo<CitationViewerModel | null>(() => {
    if (!selectedCitation || !dossierId) return null
    const citation = selectedCitation.citation
    const documentId = citation.documentId ?? citation.sourceFileId
    const document = detail?.documents.find((item) => item.id === documentId)
    return {
      dossierId,
      documentId,
      sourceFileId: citation.sourceFileId,
      citationId: citation.citationId ?? citation.lineId ?? citation.nodeId,
      scope: citation.scope ?? 'unknown',
      status: citation.status,
      quote: citation.quote || selectedCitation.text,
      pageNo: citation.pageNo ?? selectedCitation.pageNo,
      lineId: citation.lineId,
      bbox: citation.bbox,
      documentName: document?.filename ?? null,
      documentRole: document?.role ?? null,
    }
  }, [detail?.documents, dossierId, selectedCitation])

  usePageTitle(tab === 'activity' ? 'Nhật ký kiểm soát' : 'Hồ sơ hợp đồng')

  useEffect(() => {
    if (location.pathname === '/nhat-ky-phap-ly') setTab('activity')
    if (state?.tab) setTab(state.tab)
    if (state?.showSearch) {
      setQuery('Thông tin bên A')
      if (!state.tab) setTab('search')
    }
  }, [location.pathname, state])

  useEffect(() => {
    if (!dossierId) {
      setDetail(null)
      return
    }
    const controller = new AbortController()
    void getDossierStructure(dossierId, controller.signal)
      .then(setDetail)
      .catch(() => setDetail(null))
    return () => controller.abort()
  }, [dossierId])

  useEffect(() => {
    setSearchResult(null)
    setSearchError(null)
  }, [dossierId])

  useEffect(() => {
    if (tab !== 'activity' || !dossierId) {
      setReviewItems([])
      setReviewError(null)
      return
    }
    const controller = new AbortController()
    setReviewLoading(true)
    setReviewError(null)
    void listReviewItems(dossierId, controller.signal)
      .then((queue) => setReviewItems(queue.items))
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setReviewError(
          cause instanceof Error
            ? cause.message
            : 'Không tải được hàng đợi review của hồ sơ.',
        )
      })
      .finally(() => setReviewLoading(false))
    return () => controller.abort()
  }, [dossierId, tab])

  useEffect(() => {
    if (!selectedReviewItemId) {
      setRevisions([])
      return
    }
    const controller = new AbortController()
    setRevisionLoading(true)
    void listReviewRevisions(selectedReviewItemId, controller.signal)
      .then(setRevisions)
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setRevisions([])
      })
      .finally(() => setRevisionLoading(false))
    return () => controller.abort()
  }, [selectedReviewItemId])

  useEffect(() => {
    if (tab !== 'risk' || !dossierId) {
      setFacts([])
      setFindings([])
      setAnalysisError(null)
      return
    }
    const controller = new AbortController()
    setAnalysisLoading(true)
    setAnalysisError(null)
    void Promise.allSettled([
      listDossierFacts(dossierId, controller.signal),
      listDossierFindings(dossierId, controller.signal),
    ])
      .then(([factsResult, findingsResult]) => {
        if (controller.signal.aborted) return
        if (factsResult.status === 'fulfilled') setFacts(factsResult.value)
        if (findingsResult.status === 'fulfilled')
          setFindings(findingsResult.value)
        const errors = [factsResult, findingsResult]
          .filter(
            (result): result is PromiseRejectedResult =>
              result.status === 'rejected',
          )
          .map((result) =>
            result.reason instanceof Error
              ? result.reason.message
              : 'Không tải được phân tích hợp đồng.',
          )
        setAnalysisError(errors.length > 0 ? errors.join(' ') : null)
      })
      .finally(() => setAnalysisLoading(false))
    return () => controller.abort()
  }, [dossierId, tab])

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setTab('search')
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  async function handleSearch(event: FormEvent) {
    event.preventDefault()
    const question = query.trim()
    if (!question || searching) return
    if (!dossierId) {
      setSearchError('Hãy mở một hồ sơ cụ thể trước khi đặt câu hỏi.')
      return
    }
    setSearching(true)
    setSearchError(null)
    setSearchResult(null)
    try {
      setSearchResult(await searchDossier(dossierId, question))
    } catch (cause: unknown) {
      setSearchError(
        structureErrorMessage(cause) ?? 'Không hỏi được hồ sơ này. Thử lại.',
      )
    } finally {
      setSearching(false)
    }
  }

  function handleExport() {
    if (exportState !== 'idle') return
    setExportState('saving')
    if (dossierId) exportDossierEvidence(dossierId, searchResult, reviewItems)
    else exportAuditCsv()
    window.setTimeout(() => {
      setExportState('done')
      window.setTimeout(() => setExportState('idle'), 1400)
    }, 400)
  }

  function openCitation(
    hit: DossierSearchResult['hits'][number],
    index: number,
  ) {
    if (!dossierId) return
    setSelectedCitation(hit)
    navigate('/cau-truc/' + encodeURIComponent(dossierId), {
      state: {
        dossierId,
        name: detail?.name,
        focusCitation: {
          ...hit,
          index,
          citationId: hit.citation.citationId,
          scope: hit.citation.scope,
        },
      },
    })
  }

  function openStructuredEvidence(
    evidence: StructuredEvidence,
    fallbackText: string,
  ) {
    if (!dossierId || evidence.status !== 'LOCATABLE' || !evidence.pageNo)
      return
    navigate('/cau-truc/' + encodeURIComponent(dossierId), {
      state: {
        dossierId,
        name: detail?.name,
        focusCitation: {
          text: evidence.quote || fallbackText,
          pageNo: evidence.pageNo,
          sourceFileId: evidence.sourceFileId,
          lineId: evidence.lineId,
          bbox: evidence.bbox,
        },
      },
    })
  }

  async function reloadReviewQueue() {
    if (!dossierId) return
    const queue = await listReviewItems(dossierId)
    setReviewItems(queue.items)
  }

  async function handleFindingQueueAction(
    entry: FindingQueueEntry,
    action: ReviewActionType,
  ) {
    const draft = correctionDrafts[entry.item.id]?.trim()
    await submitReviewAction(entry.item.id, {
      action,
      baseVersion: entry.item.version,
      correctedValue:
        action === 'correct'
          ? { ...(entry.item.targetSnapshot ?? {}), value: draft }
          : null,
      comment: null,
    })
    setReviewMessage(`Đã ghi nhận thao tác ${action} cho mục ${entry.item.id}.`)
  }

  async function handleReviewAction(
    item: ReviewItem,
    action: ReviewActionType,
  ) {
    if (reviewActionItemId) return
    setReviewActionItemId(item.id)
    setReviewMessage(null)
    try {
      const draft = correctionDrafts[item.id]?.trim()
      await submitReviewAction(item.id, {
        action,
        baseVersion: item.version,
        correctedValue:
          action === 'correct'
            ? { ...(item.targetSnapshot ?? {}), value: draft }
            : null,
        comment: null,
      })
      await reloadReviewQueue()
      setReviewMessage(`Đã ghi nhận thao tác ${action} cho mục ${item.id}.`)
      if (selectedReviewItemId === item.id) {
        const nextRevisions = await listReviewRevisions(item.id)
        setRevisions(nextRevisions)
      }
    } catch (cause: unknown) {
      if (cause instanceof ReviewConflictError) {
        setReviewMessage(
          'Mục review đã thay đổi bởi người khác. Hàng đợi đã được tải lại; hãy kiểm tra version mới trước khi thao tác lại.',
        )
        await reloadReviewQueue().catch(() => undefined)
      } else {
        setReviewMessage(
          cause instanceof Error
            ? cause.message
            : 'Không ghi nhận được thao tác review.',
        )
      }
    } finally {
      setReviewActionItemId(null)
    }
  }

  async function handleLifecycleAction(action: 'lock' | 'approve') {
    if (!dossierId || lifecycleBusy) return
    setLifecycleBusy(true)
    setReviewMessage(null)
    try {
      if (action === 'lock') await lockDossier(dossierId)
      else await approveDossier(dossierId)
      setReviewMessage(
        action === 'lock' ? 'Đã khóa hồ sơ.' : 'Đã phê duyệt hồ sơ.',
      )
      const nextDetail = await getDossierStructure(dossierId)
      setDetail(nextDetail)
    } catch (cause: unknown) {
      setReviewMessage(
        cause instanceof Error
          ? cause.message
          : 'Không cập nhật được trạng thái hồ sơ.',
      )
    } finally {
      setLifecycleBusy(false)
    }
  }

  return (
    <div className="flex flex-col w-full space-y-space-md">
      <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col gap-space-md">
        <div className="flex flex-wrap items-center justify-between gap-space-md">
          <div className="flex items-center gap-space-sm flex-wrap">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">
              Hồ sơ hợp đồng
            </span>
            <span className="text-outline-variant font-code-sm text-code-sm">
              /
            </span>
            <div className="flex items-center gap-space-xs flex-wrap">
              <span className="font-headline-md text-headline-md text-on-surface">
                {(detail?.id ?? dossierId) || 'Chưa chọn hồ sơ'}
              </span>
              <span className="bg-surface-container-low text-on-surface-variant px-space-xs py-0.5 rounded font-label-sm text-label-sm">
                {detail?.name ?? state?.name ?? 'Hồ sơ hợp đồng'}
              </span>
            </div>
          </div>
          <button
            className="flex items-center gap-space-xs bg-surface-container hover:bg-surface-container-high text-on-surface px-space-md py-1.5 rounded font-label-md text-label-md transition-colors shadow-sm disabled:opacity-80"
            disabled={exportState !== 'idle'}
            type="button"
            onClick={handleExport}
          >
            <MaterialIcon
              name={exportState === 'saving' ? 'refresh' : 'file_download'}
              className={
                exportState === 'saving'
                  ? 'text-[16px] animate-spin'
                  : 'text-[16px]'
              }
            />
            {exportState === 'idle'
              ? 'Xuất Audit Log'
              : exportState === 'saving'
                ? 'Đang xuất...'
                : 'Đã xuất CSV'}
          </button>
        </div>

        <div className="flex items-center gap-2 text-secondary font-label-sm text-label-sm">
          <span
            className={
              'w-1.5 h-1.5 rounded-[9999px] ' +
              (dossierId ? 'bg-emerald-600' : 'bg-amber-600')
            }
          />
          {dossierId
            ? 'Đang giới hạn truy vấn trong dossier đã chọn'
            : 'Chưa chọn dossier — hãy mở hồ sơ cụ thể để hỏi AI2'}
        </div>

        <div className="flex border-b border-outline-variant/30 overflow-x-auto">
          {tabs.map((item) => {
            const active = tab === item.id
            return (
              <button
                key={item.id}
                className={
                  'relative flex items-center gap-2 px-space-md py-space-sm font-label-md text-label-md whitespace-nowrap transition-colors ' +
                  (active
                    ? 'text-primary font-semibold'
                    : 'text-secondary hover:text-primary')
                }
                type="button"
                onClick={() => {
                  if (item.id === 'clauses') {
                    navigate('/doi-soat-xung-dot', { state: { dossierId } })
                    return
                  }
                  setTab(item.id)
                }}
              >
                <MaterialIcon name={item.icon} className="text-[18px]" />
                <span>{item.label}</span>
                {item.id === 'activity' && dossierId ? (
                  <span className="bg-primary-container text-on-primary px-space-xs py-0.5 rounded font-code-sm text-code-sm font-semibold">
                    {reviewItems.length} mục
                  </span>
                ) : item.badge ? (
                  <span className="bg-primary-container text-on-primary px-space-xs py-0.5 rounded font-code-sm text-code-sm font-semibold">
                    {item.badge}
                  </span>
                ) : null}
                {active ? (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-container" />
                ) : null}
              </button>
            )
          })}
        </div>
      </div>

      {tab === 'search' ? (
        <>
          <div className="w-full flex flex-col items-center justify-center py-1 gap-2">
            <form
              className="w-full max-w-3xl relative flex items-center bg-surface-container-lowest border border-outline-variant/40 shadow-md px-4 py-2 group focus-within:border-primary focus-within:shadow-lg"
              style={{ borderRadius: '9999px' }}
              onSubmit={(event) => void handleSearch(event)}
            >
              <MaterialIcon
                name="search"
                className="text-[22px] text-secondary group-focus-within:text-primary transition-colors mr-3 flex-shrink-0"
              />
              <input
                ref={searchRef}
                className="w-full bg-transparent text-on-surface font-body-md text-body-md placeholder:text-secondary focus:outline-none border-none py-1"
                placeholder="Đặt câu hỏi trong hồ sơ này..."
                type="search"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value)
                  setSearchError(null)
                  if (!event.target.value.trim()) setSearchResult(null)
                }}
              />
              <span className="font-code-sm text-[11px] text-secondary bg-surface-container-low px-2 py-0.5 border border-outline-variant/20 tracking-wide font-medium rounded-full">
                Ctrl K
              </span>
            </form>

            {searching ? (
              <div className="flex items-center gap-2 font-label-sm text-label-sm text-secondary pt-1">
                <MaterialIcon
                  name="refresh"
                  className="text-[16px] animate-spin"
                />
                Đang hỏi AI2 trên snapshot của hồ sơ...
              </div>
            ) : searchError ? (
              <div
                className="font-label-sm text-label-sm text-error pt-1"
                role="alert"
              >
                {searchError}
              </div>
            ) : searchResult ? (
              <div className="font-label-sm text-label-sm text-secondary pt-1">
                {searchResult.hits.length} evidence · trạng thái{' '}
                {searchResult.reviewState}
              </div>
            ) : (
              <button
                className="font-label-sm text-label-sm text-secondary hover:text-primary transition-colors pt-1"
                type="button"
                onClick={() => {
                  setQuery('Thông tin bên A')
                  searchRef.current?.focus()
                }}
              >
                Gợi ý: Thông tin bên A
              </button>
            )}
          </div>

          {searchResult ? (
            <div className="space-y-space-md">
              <DossierSearchResults
                result={searchResult}
                onSelectCitation={openCitation}
              />
              {contextPanelModel ? (
                <ContextFindingsPanel model={contextPanelModel} />
              ) : null}
              <DynamicCitationViewer citation={viewerCitation} />
            </div>
          ) : dossierId ? (
            <DossierStructurePreview
              dossierId={dossierId}
              title={detail?.name ?? 'Hồ sơ hợp đồng'}
            />
          ) : null}
        </>
      ) : null}

      {tab === 'activity' ? (
        dossierId ? (
          <section className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm space-y-space-md">
            <div className="flex flex-wrap items-center justify-between gap-space-sm">
              <div>
                <h2 className="font-headline-md text-headline-md text-on-surface">
                  Hàng đợi Human-in-the-loop
                </h2>
                <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
                  Mọi thao tác đều gửi kèm version hiện tại và được ghi vào
                  revision timeline.
                </p>
              </div>
              <div className="flex gap-space-xs">
                <button
                  className="px-space-sm py-space-xs rounded bg-surface-container text-on-surface font-label-sm disabled:opacity-50"
                  type="button"
                  disabled={lifecycleBusy}
                  onClick={() => void handleLifecycleAction('lock')}
                >
                  Khóa hồ sơ
                </button>
                <button
                  className="px-space-sm py-space-xs rounded bg-primary text-on-primary font-label-sm disabled:opacity-50"
                  type="button"
                  disabled={lifecycleBusy}
                  onClick={() => void handleLifecycleAction('approve')}
                >
                  Phê duyệt
                </button>
              </div>
            </div>

            {reviewMessage ? (
              <div
                className="rounded bg-surface-container-low px-space-sm py-space-xs font-body-sm text-body-sm text-on-surface"
                role="status"
              >
                {reviewMessage}
              </div>
            ) : null}
            {!reviewLoading && !reviewError ? (
              <FindingQueue
                entries={findingQueueEntries}
                onAction={handleFindingQueueAction}
                onReload={reloadReviewQueue}
              />
            ) : null}
            {reviewLoading ? (
              <div className="font-body-sm text-body-sm text-secondary">
                Đang tải hàng đợi review...
              </div>
            ) : reviewError ? (
              <div
                className="font-body-sm text-body-sm text-error"
                role="alert"
              >
                {reviewError}
              </div>
            ) : reviewItems.length === 0 ? (
              <div className="rounded border border-outline-variant/30 p-space-md font-body-sm text-body-sm text-secondary">
                Không còn review item mở cho hồ sơ này.
              </div>
            ) : (
              <div className="space-y-space-sm">
                {reviewItems.map((item) => {
                  const selected = selectedReviewItemId === item.id
                  const draft = correctionDrafts[item.id] ?? ''
                  return (
                    <article
                      key={item.id}
                      className="rounded border border-outline-variant/30 p-space-md space-y-space-sm"
                    >
                      <button
                        className="w-full text-left"
                        type="button"
                        onClick={() =>
                          setSelectedReviewItemId(selected ? null : item.id)
                        }
                      >
                        <div className="flex flex-wrap items-center gap-space-xs font-label-sm text-label-sm">
                          <span className="font-semibold text-primary">
                            {item.priority}
                          </span>
                          <span className="text-secondary">
                            {item.targetType}/{item.targetId}
                          </span>
                          <span className="text-secondary">
                            version {item.version}
                          </span>
                          <span className="text-secondary">{item.status}</span>
                        </div>
                        <p className="font-body-md text-body-md text-on-surface mt-space-xs">
                          {item.reason || 'Cần người kiểm tra.'}
                        </p>
                        {item.targetSnapshot ? (
                          <pre className="mt-space-xs overflow-auto rounded bg-surface-container-low p-space-xs font-code-sm text-code-sm text-secondary">
                            {JSON.stringify(item.targetSnapshot, null, 2)}
                          </pre>
                        ) : null}
                      </button>
                      <div className="flex flex-wrap items-center gap-space-xs">
                        <button
                          className="px-space-sm py-space-xs rounded bg-emerald-100 text-emerald-900 font-label-sm disabled:opacity-50"
                          type="button"
                          disabled={reviewActionItemId !== null}
                          onClick={() =>
                            void handleReviewAction(item, 'confirm')
                          }
                        >
                          Xác nhận
                        </button>
                        <input
                          className="min-w-48 flex-1 rounded border border-outline-variant/40 bg-transparent px-space-sm py-space-xs font-body-sm text-body-sm"
                          placeholder="Giá trị chỉnh sửa"
                          value={draft}
                          onChange={(event) =>
                            setCorrectionDrafts((current) => ({
                              ...current,
                              [item.id]: event.target.value,
                            }))
                          }
                        />
                        <button
                          className="px-space-sm py-space-xs rounded bg-amber-100 text-amber-900 font-label-sm disabled:opacity-50"
                          type="button"
                          disabled={!draft || reviewActionItemId !== null}
                          onClick={() =>
                            void handleReviewAction(item, 'correct')
                          }
                        >
                          Sửa
                        </button>
                        <button
                          className="px-space-sm py-space-xs rounded bg-red-100 text-red-900 font-label-sm disabled:opacity-50"
                          type="button"
                          disabled={reviewActionItemId !== null}
                          onClick={() =>
                            void handleReviewAction(item, 'reject')
                          }
                        >
                          Từ chối
                        </button>
                        <button
                          className="px-space-sm py-space-xs rounded bg-surface-container text-on-surface font-label-sm disabled:opacity-50"
                          type="button"
                          disabled={reviewActionItemId !== null}
                          onClick={() =>
                            void handleReviewAction(item, 'needs_more_evidence')
                          }
                        >
                          Cần thêm bằng chứng
                        </button>
                      </div>
                      {selected ? (
                        <div className="border-t border-outline-variant/20 pt-space-sm">
                          <h3 className="font-label-md text-label-md text-on-surface">
                            Revision timeline
                          </h3>
                          {revisionLoading ? (
                            <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
                              Đang tải lịch sử...
                            </p>
                          ) : revisions.length === 0 ? (
                            <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
                              Chưa có revision.
                            </p>
                          ) : (
                            <ol className="mt-space-xs space-y-space-xs">
                              {revisions.map((revision) => (
                                <li
                                  key={`${revision.revisionNumber}-${revision.createdAt}`}
                                  className="font-body-sm text-body-sm text-secondary"
                                >
                                  <span className="font-semibold text-on-surface">
                                    #{revision.revisionNumber} {revision.action}
                                  </span>{' '}
                                  · {revision.authorUserId || 'unknown'}
                                  {revision.comment
                                    ? ` · ${revision.comment}`
                                    : ''}
                                </li>
                              ))}
                            </ol>
                          )}
                        </div>
                      ) : null}
                    </article>
                  )
                })}
              </div>
            )}
          </section>
        ) : (
          <DossierAuditLog />
        )
      ) : null}

      {tab === 'risk' ? (
        dossierId ? (
          <section className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm space-y-space-lg">
            <div>
              <h2 className="font-headline-md text-headline-md text-on-surface">
                Phân tích hợp đồng có cấu trúc
              </h2>
              <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
                Facts và findings lấy trực tiếp từ API extraction/conflict; dòng
                nào thiếu nguồn sẽ giữ trạng thái an toàn.
              </p>
            </div>
            {analysisLoading ? (
              <p className="font-body-sm text-body-sm text-secondary">
                Đang tải facts và findings...
              </p>
            ) : null}
            {analysisError ? (
              <p className="font-body-sm text-body-sm text-error" role="alert">
                {analysisError}
              </p>
            ) : null}
            <div>
              <h3 className="font-title-sm text-title-sm text-on-surface">
                Facts / fields ({facts.length})
              </h3>
              {facts.length === 0 ? (
                <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
                  Chưa có fact có cấu trúc cho hồ sơ này.
                </p>
              ) : (
                <div className="mt-space-sm grid gap-space-sm md:grid-cols-2">
                  {facts.map((fact) => {
                    const value =
                      typeof fact.effectiveValue === 'string'
                        ? fact.effectiveValue
                        : JSON.stringify(fact.effectiveValue)
                    const canOpen = fact.evidence.status === 'LOCATABLE'
                    return (
                      <article
                        key={fact.id}
                        className="rounded border border-outline-variant/30 p-space-sm"
                      >
                        <div className="flex items-center justify-between gap-space-xs">
                          <span className="font-label-md text-label-md font-semibold text-on-surface">
                            {fact.key}
                          </span>
                          <span className="font-code-sm text-code-sm text-secondary">
                            {Math.round(fact.confidence * 100)}% ·{' '}
                            {fact.reviewState}
                          </span>
                        </div>
                        <p className="mt-space-xs font-body-md text-body-md text-on-surface">
                          {value || 'Chưa có giá trị'}
                        </p>
                        <div className="mt-space-xs flex items-center justify-between gap-space-xs font-body-sm text-body-sm text-secondary">
                          <span>
                            {fact.evidence.status}
                            {fact.evidence.citationId
                              ? ` · ${fact.evidence.citationId}`
                              : ''}
                          </span>
                          {canOpen ? (
                            <button
                              className="text-primary underline"
                              type="button"
                              onClick={() =>
                                openStructuredEvidence(
                                  fact.evidence,
                                  fact.rawText,
                                )
                              }
                            >
                              Mở nguồn
                            </button>
                          ) : null}
                        </div>
                        {fact.evidence.quote ? (
                          <p className="mt-space-xs line-clamp-2 font-body-sm text-body-sm text-secondary">
                            “{fact.evidence.quote}”
                          </p>
                        ) : null}
                      </article>
                    )
                  })}
                </div>
              )}
            </div>
            <div>
              <h3 className="font-title-sm text-title-sm text-on-surface">
                Findings / risk ({findings.length})
              </h3>
              {findings.length === 0 ? (
                <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
                  Chưa có finding so sánh hoặc xung đột.
                </p>
              ) : (
                <div className="mt-space-sm space-y-space-sm">
                  {findings.map((finding) => (
                    <article
                      key={finding.id}
                      className="rounded border border-outline-variant/30 p-space-sm"
                    >
                      <div className="flex flex-wrap items-center gap-space-xs font-label-sm text-label-sm">
                        <span className="font-semibold text-on-surface">
                          {finding.topic}
                        </span>
                        <span className="text-secondary">{finding.scope}</span>
                        <span className="text-secondary">
                          {finding.severity}
                        </span>
                      </div>
                      <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
                        {finding.rationale ||
                          'Không có diễn giải; cần kiểm tra nguồn.'}
                      </p>
                      <div className="mt-space-sm grid gap-space-xs md:grid-cols-2">
                        {finding.sides.map((side, index) => (
                          <div
                            key={`${finding.id}-${side.documentId}-${index}`}
                            className="rounded bg-surface-container-low p-space-xs font-body-sm text-body-sm"
                          >
                            <div className="flex justify-between gap-space-xs">
                              <span>
                                {side.documentRole || side.side || 'Nguồn'}
                              </span>
                              <span className="text-secondary">
                                {side.evidence.status}
                              </span>
                            </div>
                            <p className="mt-1">
                              {typeof side.valueSnapshot === 'string'
                                ? side.valueSnapshot
                                : JSON.stringify(side.valueSnapshot)}
                            </p>
                            {side.evidence.status === 'LOCATABLE' ? (
                              <button
                                className="mt-1 text-primary underline"
                                type="button"
                                onClick={() =>
                                  openStructuredEvidence(
                                    side.evidence,
                                    String(side.valueSnapshot ?? ''),
                                  )
                                }
                              >
                                Mở nguồn
                              </button>
                            ) : null}
                          </div>
                        ))}
                      </div>
                      <p className="mt-space-xs font-code-sm text-code-sm text-secondary">
                        {finding.disclaimer}
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </div>
          </section>
        ) : (
          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm">
            <h2 className="font-headline-md text-headline-md text-on-surface">
              Đánh giá Rủi ro
            </h2>
            <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
              Hãy mở một hồ sơ cụ thể để tải facts và findings có nguồn.
            </p>
          </div>
        )
      ) : null}
    </div>
  )
}
