import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  contractDocument,
  getDossierStructure,
  listClauses,
  listReviewSpots,
  structureErrorMessage,
  type ClauseNode,
  type ClauseRegion,
  type DossierStructure,
  type ReviewSpot,
  type ReviewSpotLink,
  type StructureDocument,
} from '../api/structure'
import {
  listReviewItems,
  submitReviewAction,
  type ReviewItem,
} from '../api/review'
import { dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { ConflictDocumentPane } from '../components/ConflictDocumentPane'
import { MaterialIcon } from '../components/icons'
import { clauseConflicts } from '../data/clauseConflicts'
import { structurePath } from '../data/dossiers'
import { usePageTitle } from '../hooks/usePageTitle'
import { findClause, findClauseByQuote } from '../structure/citations'
import { bodyOf, headOf } from '../structure/display'

type Verdict = 'correct' | 'deviation' | 'edit'

const REVIEW_ACTION = {
  correct: 'confirm',
  deviation: 'reject',
  edit: 'correct',
} as const
type ReviewCard = {
  id: string
  title: string
  quote: string
  contrast: string
  basis: string
  pageNo: number | null
  confidence: number | null
  regions: ClauseRegion[]
  review: ReviewSpotLink | null
}

function pageFromText(text: string) {
  const match = text.match(/trang\s+(\d+)/i)
  return match ? Number(match[1]) : null
}

function confidenceLabel(value: number | null) {
  if (value === null || !Number.isFinite(value)) return null
  const percent = value <= 1 ? value * 100 : value
  return `${percent.toFixed(1)}%`
}

function sideText(side: { value: string; quote: string }) {
  const quote = side.quote.trim()
  if (quote) return quote
  const value = side.value.trim()
  return value && value !== '—' ? value : ''
}

function basisOf(head: string, pageNo: number | null, pageCount: number) {
  const page =
    pageNo && pageNo > 0
      ? `Trang ${pageNo}${pageCount > 0 ? `/${pageCount}` : ''}`
      : ''
  if (head && page) return `Căn cứ: ${head} (${page})`
  if (head) return `Căn cứ: ${head}`
  if (page) return `Căn cứ: ${page}`
  return 'Căn cứ: trong hồ sơ'
}

function spotToCard(
  spot: ReviewSpot,
  nodes: ClauseNode[],
  pageCount: number,
): ReviewCard {
  const linked =
    spot.clauseIds
      .map((id) => findClause(nodes, id))
      .find((node): node is ClauseNode => node !== null) ?? null
  const texts = spot.sides.map(sideText).filter(Boolean)
  const matched =
    linked ??
    (texts[0] ? findClauseByQuote(nodes, texts[0], null) : null)
  const quote =
    texts.find((text) => {
      if (!matched) return false
      const body = bodyOf(matched)
      return body.includes(text) || text.includes(body.slice(0, 40))
    }) ||
    texts[0] ||
    (matched ? bodyOf(matched) : '') ||
    spot.rationale
  const contrast = texts.find((text) => text !== quote) ?? ''
  const pageNo =
    (matched?.pageStart && matched.pageStart > 0 ? matched.pageStart : null) ??
    pageFromText(spot.topic) ??
    pageFromText(quote)
  const head = matched ? headOf(matched) : ''
  return {
    id: spot.id,
    title: spot.topic || head || 'Chỗ cần đối soát',
    quote,
    contrast,
    basis: basisOf(head, pageNo, pageCount),
    pageNo,
    confidence: matched?.confidence ?? null,
    regions: matched?.regions ?? [],
    review: spot.review,
  }
}

function demoCards(): ReviewCard[] {
  return clauseConflicts.map((conflict) => {
    const quote = `${conflict.source1.quoteBefore}${conflict.source1.highlight}${conflict.source1.quoteAfter}`.trim()
    const contrast = `${conflict.source2.quoteBefore}${conflict.source2.highlight}${conflict.source2.quoteAfter}`.trim()
    const pageNo =
      pageFromText(conflict.source1.location) ?? pageFromText(conflict.location)
    return {
      id: conflict.id,
      title: conflict.title,
      quote,
      contrast,
      basis: basisOf('', pageNo, 0),
      pageNo,
      confidence: null,
      regions: [],
      review: null,
    }
  })
}

function VerdictButton({
  active,
  icon,
  label,
  iconClass,
  onClick,
}: {
  active: boolean
  icon: string
  label: string
  iconClass: string
  onClick: () => void
}) {
  return (
    <button
      className={`flex h-7 items-center justify-center gap-1 rounded px-2 font-label-sm text-label-sm transition-colors ${
        active
          ? 'bg-primary-container text-on-primary'
          : 'border border-outline-variant/70 bg-surface-container-lowest text-on-surface hover:bg-surface-container'
      }`}
      type="button"
      onClick={onClick}
    >
      <MaterialIcon name={icon} className={`text-[14px] ${active ? '' : iconClass}`} />
      <span>{label}</span>
    </button>
  )
}

export function ClauseConflictPage() {
  usePageTitle('Đối soát xung đột')
  const navigate = useNavigate()
  const location = useLocation()
  const reviewState = location.state as {
    dossierId?: string
    name?: string
  } | null
  const dossierId = reviewState?.dossierId ?? ''
  const { user } = useAuth()
  const searchRef = useRef<HTMLInputElement>(null)
  const [detail, setDetail] = useState<DossierStructure | null>(null)
  const [document, setDocument] = useState<StructureDocument | null>(null)
  const [spots, setSpots] = useState<ReviewSpot[]>([])
  const [nodes, setNodes] = useState<ClauseNode[]>([])
  const [pdfPages, setPdfPages] = useState(0)
  const [loading, setLoading] = useState(Boolean(dossierId))
  const [error, setError] = useState<string | null>(null)
  const [activeId, setActiveId] = useState('')
  const [pageNo, setPageNo] = useState(1)
  const [query, setQuery] = useState('')
  const [verdicts, setVerdicts] = useState<Record<string, Verdict>>({})
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [reviewByFinding, setReviewByFinding] = useState<
    Record<string, ReviewItem>
  >({})
  const [savingId, setSavingId] = useState<string | null>(null)
  const [savedIds, setSavedIds] = useState<Record<string, boolean>>({})
  const [reviewVersions, setReviewVersions] = useState<Record<string, number>>({})
  const [notice, setNotice] = useState<{
    text: string
    tone: 'ok' | 'error'
  } | null>(null)
  const backTo = dossierId
    ? structurePath(dossierId)
    : user
      ? dossiersPath(user.role)
      : '/'

  useEffect(() => {
    if (!dossierId) return
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    Promise.all([
      getDossierStructure(dossierId, controller.signal),
      listReviewSpots(dossierId, controller.signal),
      listReviewItems(dossierId, controller.signal).catch(() => ({
        items: [] as ReviewItem[],
      })),
    ])
      .then(async ([nextDetail, nextSpots, queue]) => {
        if (controller.signal.aborted) return
        const linked: Record<string, ReviewItem> = {}
        for (const item of queue.items) {
          if (item.targetType === 'finding' && item.targetId) {
            linked[item.targetId] = item
          }
        }
        setReviewByFinding(linked)
        setDetail(nextDetail)
        const nextDocument = contractDocument(nextDetail)
        setDocument(nextDocument)
        if (!nextDocument) {
          setNodes([])
          setSpots(nextSpots)
          return
        }
        try {
          const nextNodes = await listClauses(nextDocument.id, controller.signal)
          if (controller.signal.aborted) return
          setNodes(nextNodes)
        } catch {
          if (controller.signal.aborted) return
          setNodes([])
        }
        setSpots(nextSpots)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(structureErrorMessage(cause))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [dossierId])

  const pageCount = document?.pageCount || pdfPages
  const cards = useMemo(() => {
    if (!dossierId) return demoCards()
    return spots.map((spot) => spotToCard(spot, nodes, pageCount))
  }, [dossierId, nodes, pageCount, spots])

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return cards
    return cards.filter((card) =>
      `${card.title} ${card.quote} ${card.basis}`.toLowerCase().includes(term),
    )
  }, [cards, query])

  const active =
    cards.find((card) => card.id === activeId) ?? visible[0] ?? cards[0] ?? null

  useEffect(() => {
    if (cards.length === 0) return
    if (!cards.some((card) => card.id === activeId)) setActiveId(cards[0].id)
  }, [activeId, cards])

  useEffect(() => {
    if (active?.pageNo) setPageNo(active.pageNo)
  }, [active?.id, active?.pageNo])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const onPageCount = useCallback((count: number) => {
    setPdfPages((current) => (current === count ? current : count))
  }, [])
  const onPageChange = useCallback((page: number) => {
    setPageNo(Math.max(1, page))
  }, [])

  const reviewed = cards.filter((card) => verdicts[card.id]).length
  const confidences = cards
    .map((card) => card.confidence)
    .filter((value): value is number => value !== null)
  const average =
    confidences.length === 0
      ? null
      : confidences.reduce((sum, value) => sum + value, 0) / confidences.length
  const dossierName =
    detail?.name?.trim() || reviewState?.name?.trim() || 'Hồ sơ hợp đồng'

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 4000)
    return () => window.clearTimeout(timer)
  }, [notice])

  function choose(id: string, verdict: Verdict) {
    setVerdicts((current) => ({ ...current, [id]: verdict }))
    setSavedIds((current) => ({ ...current, [id]: false }))
    setNotice(null)
  }

  async function saveCard(id: string) {
    const verdict = verdicts[id]
    if (!verdict || savingId) return
    const note = (notes[id] ?? '').trim()
    if (verdict === 'edit' && !note) {
      setNotice({
        text: 'Sửa nhận định cần nhập ghi chú trước khi lưu.',
        tone: 'error',
      })
      return
    }
    const card = cards.find((item) => item.id === id)
    let linked = reviewByFinding[id]
    let itemId = card?.review?.itemId || linked?.id
    let version =
      reviewVersions[id] ?? card?.review?.version ?? linked?.version
    setSavingId(id)
    setNotice(null)
    try {
      if (!itemId && dossierId) {
        const queue = await listReviewItems(dossierId)
        const match = queue.items.find(
          (item) => item.targetType === 'finding' && item.targetId === id,
        )
        if (match) {
          linked = match
          itemId = match.id
          version = version ?? match.version
          setReviewByFinding((current) => ({ ...current, [id]: match }))
        }
      }
      if (!itemId || version === undefined) {
        setNotice({
          text: 'Mục này chưa có bản ghi thẩm định để lưu.',
          tone: 'error',
        })
        return
      }
      const result = await submitReviewAction(itemId, {
        baseVersion: version,
        action: REVIEW_ACTION[verdict],
        comment: note || null,
        correctedValue: verdict === 'edit' ? { assessment: note } : null,
      })
      setReviewVersions((current) => ({ ...current, [id]: result.newVersion }))
      if (linked) {
        setReviewByFinding((current) => ({
          ...current,
          [id]: {
            ...linked,
            version: result.newVersion,
            status: result.itemStatus,
          },
        }))
      }
      setSavedIds((current) => ({ ...current, [id]: true }))
      setNotice({ text: 'Đã lưu nhận định.', tone: 'ok' })
    } catch (cause: unknown) {
      setNotice({
        text: cause instanceof Error ? cause.message : 'Không lưu được nhận định.',
        tone: 'error',
      })
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col">
      <section className="mb-space-sm w-full shrink-0 border-b border-outline-variant/40 bg-surface-container-lowest px-gutter py-space-sm">
        <div className="flex flex-wrap items-center justify-between gap-space-sm">
          <div className="flex flex-wrap items-center gap-space-md">
            <div className="flex items-center gap-space-xs font-label-md text-label-md text-secondary">
              <span>Hồ sơ Hợp đồng</span>
              <span className="text-outline-variant">/</span>
              <span className="font-semibold text-on-surface">{dossierName}</span>
            </div>
            {document ? (
              <div className="hidden items-center gap-space-sm font-label-sm text-label-sm text-secondary lg:flex">
                <span className="font-medium text-on-surface">
                  {document.filename}
                </span>
                {pageCount > 0 ? (
                  <span className="font-code-sm text-code-sm text-on-surface-variant">
                    {pageCount} trang
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <div className="grid min-h-0 w-full flex-1 grid-cols-1 overflow-hidden rounded border border-outline-variant/50 bg-surface-container-low shadow-sm xl:grid-cols-12">
          <div className="flex min-h-[420px] flex-col border-r border-outline-variant/60 xl:col-span-7 xl:min-h-0">
            <ConflictDocumentPane
              citeNo={active ? cards.findIndex((card) => card.id === active.id) + 1 : null}
              documentId={document?.id ?? null}
              filename={document?.filename ?? ''}
              pageCount={pageCount}
              pageNo={pageNo}
              quote={active?.quote ?? ''}
              regions={active?.regions ?? []}
              title={active?.title ?? ''}
              onBack={() => navigate(backTo)}
              onPageChange={onPageChange}
              onPageCount={onPageCount}
            />
          </div>
          <div className="flex min-h-[420px] flex-col bg-surface-container-lowest xl:col-span-5 xl:min-h-0">
            <div className="space-y-space-sm border-b border-outline-variant/40 bg-surface-bright p-space-md">
              <div className="relative">
                <MaterialIcon
                  name="search"
                  className="absolute left-2.5 top-2.5 text-[18px] text-secondary"
                />
                <input
                  ref={searchRef}
                  className="h-9 w-full rounded border border-outline-variant/60 bg-surface-container-low pl-9 pr-14 font-body-sm text-body-sm text-on-surface outline-none focus:border-primary-container focus:ring-1 focus:ring-primary-container"
                  placeholder="Lọc trích dẫn cần đối soát..."
                  type="text"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
                <span className="absolute right-2 top-2 rounded bg-surface-container px-1.5 py-0.5 font-code-sm text-code-sm text-secondary">
                  Ctrl+K
                </span>
              </div>
              <div className="flex items-center justify-between pt-0.5 font-label-sm text-label-sm">
                <div className="flex items-center gap-1.5 font-semibold uppercase tracking-wider text-primary-container">
                  <MaterialIcon
                    name="fact_check"
                    className="text-[16px] text-primary-container"
                  />
                  <span>
                    Câu trả lời tổng hợp & {cards.length} điểm trích dẫn
                  </span>
                </div>
                {confidenceLabel(average) ? (
                  <span className="font-code-sm text-code-sm text-secondary">
                    Độ chuẩn xác {confidenceLabel(average)}
                  </span>
                ) : null}
              </div>
              {cards.length > 0 ? (
                <div className="rounded border border-outline-variant/30 bg-surface-container-low p-space-sm font-body-sm text-body-sm leading-snug text-on-surface-variant">
                  Hồ sơ cần đối soát{' '}
                  {cards.map((card, index) => (
                    <span key={card.id}>
                      {index > 0
                        ? index === cards.length - 1
                          ? ' và '
                          : ', '
                        : ''}
                      {card.title}{' '}
                      <button
                        className={`mx-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full font-code-sm text-[10px] font-bold ${
                          card.id === active?.id
                            ? 'bg-primary-container text-on-primary'
                            : 'bg-secondary text-on-secondary'
                        }`}
                        type="button"
                        onClick={() => setActiveId(card.id)}
                      >
                        {index + 1}
                      </button>
                    </span>
                  ))}
                  .
                </div>
              ) : null}
            </div>
            <div className="flex-1 space-y-space-sm overflow-y-auto p-space-md">
              {loading ? (
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Đang tải các chỗ cần kiểm tra…
                </p>
              ) : null}
              {error ? (
                <p className="font-body-sm text-body-sm text-error">{error}</p>
              ) : null}
              {!loading && dossierId && cards.length === 0 ? (
                <section className="flex flex-col items-start gap-space-sm rounded bg-surface-container-low p-space-md">
                  <h2 className="font-title-sm text-title-sm text-on-surface">
                    Không có mục đối soát
                  </h2>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">
                    Hồ sơ này không có chỗ cần chọn nguồn. Các chỗ cần xử lý,
                    nếu có, nằm trên cây cấu trúc.
                  </p>
                  <button
                    className="flex h-10 items-center rounded-lg bg-primary px-space-lg font-body-sm text-body-sm font-semibold text-on-primary"
                    type="button"
                    onClick={() => navigate(backTo)}
                  >
                    Về cấu trúc cây
                  </button>
                </section>
              ) : null}
              {visible.map((card) => {
                const index = cards.findIndex((item) => item.id === card.id) + 1
                const selected = card.id === active?.id
                const verdict = verdicts[card.id]
                return (
                  <article
                    key={card.id}
                    className={
                      selected
                        ? 'relative rounded border-y border-r border-l-4 border-outline-variant/50 border-l-primary-container bg-blue-50/50 p-space-md shadow-sm'
                        : 'rounded border border-outline-variant/50 bg-surface-container-lowest p-space-md hover:border-outline'
                    }
                  >
                    <div className="mb-space-xs flex items-start justify-between gap-space-sm">
                      <button
                        className="flex items-center gap-space-sm text-left"
                        type="button"
                        onClick={() => setActiveId(card.id)}
                      >
                        <span
                          className={`flex h-5 w-5 items-center justify-center rounded-full font-code-sm text-code-sm font-bold ${
                            selected
                              ? 'bg-primary-container text-on-primary shadow-sm'
                              : 'bg-secondary text-on-secondary'
                          }`}
                        >
                          {index}
                        </span>
                        <span
                          className={`font-label-md text-label-md font-semibold ${
                            selected ? 'text-primary-container' : 'text-on-surface'
                          }`}
                        >
                          {card.title}
                        </span>
                      </button>
                      {selected ? (
                        <span className="inline-flex items-center gap-1 rounded bg-primary-container px-1.5 py-0.5 font-label-sm text-[10px] font-semibold uppercase text-on-primary">
                          <MaterialIcon name="visibility" className="text-[12px]" />
                          Đang xem trên PDF
                        </span>
                      ) : card.pageNo ? (
                        <button
                          className="flex items-center gap-0.5 font-label-sm text-label-sm text-secondary hover:text-primary-container"
                          type="button"
                          onClick={() => setActiveId(card.id)}
                        >
                          <span>Đến trang {card.pageNo}</span>
                          <MaterialIcon name="arrow_forward" className="text-[14px]" />
                        </button>
                      ) : null}
                    </div>
                    <p
                      className={`mb-space-sm rounded border p-2 font-body-sm text-body-sm leading-normal ${
                        selected
                          ? 'border-outline-variant/30 bg-white/80 font-medium text-on-surface'
                          : 'border-outline-variant/20 bg-surface-container-low/60 text-on-surface-variant'
                      }`}
                    >
                      “{card.quote || 'Không có trích dẫn.'}”
                    </p>
                    {card.contrast ? (
                      <p className="mb-space-sm font-body-sm text-body-sm text-on-surface-variant">
                        Đối chiếu: {card.contrast}
                      </p>
                    ) : null}
                    <div className="mb-space-sm flex flex-wrap items-center justify-between gap-space-xs border-t border-outline-variant/30 pt-space-xs font-label-sm text-label-sm text-secondary">
                      <span className="font-code-sm text-code-sm font-medium text-on-surface-variant">
                        {card.basis}
                      </span>
                      {confidenceLabel(card.confidence) ? (
                        <span className="font-code-sm text-code-sm font-semibold text-tertiary-container">
                          Độ tin cậy: {confidenceLabel(card.confidence)}
                        </span>
                      ) : null}
                    </div>
                    <div className="grid grid-cols-3 gap-1.5">
                      <VerdictButton
                        active={verdict === 'correct'}
                        icon="check"
                        iconClass="text-tertiary-container"
                        label="Chính xác"
                        onClick={() => choose(card.id, 'correct')}
                      />
                      <VerdictButton
                        active={verdict === 'deviation'}
                        icon="close"
                        iconClass="text-error"
                        label="Sai lệch"
                        onClick={() => choose(card.id, 'deviation')}
                      />
                      <VerdictButton
                        active={verdict === 'edit'}
                        icon="edit"
                        iconClass="text-secondary"
                        label={selected ? 'Sửa nhận định' : 'Sửa'}
                        onClick={() => choose(card.id, 'edit')}
                      />
                    </div>
                    {verdict === 'edit' ? (
                      <textarea
                        className="mt-2 w-full resize-none rounded bg-surface-container-low p-2 font-body-sm text-body-sm text-on-surface outline-none focus:ring-1 focus:ring-outline-variant"
                        placeholder="Ghi chú thẩm định..."
                        rows={2}
                        value={notes[card.id] ?? ''}
                        onChange={(event) => {
                          setSavedIds((current) => ({
                            ...current,
                            [card.id]: false,
                          }))
                          setNotes((current) => ({
                            ...current,
                            [card.id]: event.target.value,
                          }))
                        }}
                      />
                    ) : null}
                    {verdict ? (
                      <div className="mt-2 flex items-center justify-end">
                        <button
                          className="inline-flex items-center gap-1 rounded bg-primary px-3 py-1.5 font-label-sm text-label-sm font-semibold text-on-primary disabled:opacity-60"
                          disabled={savingId === card.id}
                          type="button"
                          onClick={() => void saveCard(card.id)}
                        >
                          <MaterialIcon
                            name={savedIds[card.id] ? 'check' : 'save'}
                            className="text-[15px]"
                          />
                          {savingId === card.id
                            ? 'Đang lưu...'
                            : savedIds[card.id]
                              ? 'Đã lưu'
                              : 'Lưu mục này'}
                        </button>
                      </div>
                    ) : null}
                  </article>
                )
              })}
            </div>
            <div className="flex items-center justify-between border-t border-outline-variant/40 bg-surface-container-low p-space-sm font-label-sm text-label-sm text-secondary">
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-tertiary-container" />
                Đã thẩm định {reviewed}/{cards.length} trích dẫn
              </span>
            </div>
          </div>
      </div>
      {notice ? (
        <div
          className="fixed top-20 right-6 z-[70] flex w-[min(24rem,calc(100vw-3rem))] items-start gap-space-md rounded border border-surface-container bg-surface-container-lowest px-space-lg py-space-md font-body-sm text-body-sm text-on-surface shadow-md"
          role="status"
        >
          <MaterialIcon
            name={notice.tone === 'error' ? 'error' : 'check_circle'}
            className={`shrink-0 text-[20px] ${
              notice.tone === 'error' ? 'text-error' : 'text-emerald-600'
            }`}
          />
          <span className="flex-1">{notice.text}</span>
          <button
            aria-label="Đóng thông báo"
            className="shrink-0 text-secondary hover:text-on-surface"
            type="button"
            onClick={() => setNotice(null)}
          >
            <MaterialIcon name="close" className="text-[18px]" />
          </button>
        </div>
      ) : null}
    </div>
  )
}
