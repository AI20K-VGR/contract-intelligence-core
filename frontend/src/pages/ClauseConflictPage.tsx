import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { clauseOrdinal } from '../api/clauseReview'
import {
  contractDocument,
  getDossierStructure,
  listClauses,
  listReviewSpots,
  loadDocumentLines,
  structureErrorMessage,
  type ClauseNode,
  type ClauseRegion,
  type DossierStructure,
  type ReviewSpot,
  type ReviewSpotLink,
  type ReviewSpotSide,
  type StructureDocument,
} from '../api/structure'
import { dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { ClauseFrameResults } from '../components/ClauseFrameResults'
import {
  ConflictFindingReview,
  type LinkedClause,
} from '../components/ConflictFindingReview'
import {
  ConflictDocumentPane,
  type ConflictBox,
} from '../components/ConflictDocumentPane'
import { MaterialIcon } from '../components/icons'
import { clauseConflicts } from '../data/clauseConflicts'
import { structurePath } from '../data/dossiers'
import { usePageTitle } from '../hooks/usePageTitle'
import { findClause, findClauseByQuote } from '../structure/citations'
import { bodyOf, headOf } from '../structure/display'
import { clauseForCitation, regionsOf } from '../structure/conflictCite'
import { reviewTargetNode } from '../structure/reviewTarget'
import { buildStructureTree } from '../structure'
import {
  conflictKind,
  withinDocumentId,
  withinSideLabel,
  type ConflictKind,
} from '../structure/withinDocument'
import type { OcrLine } from '../structure/types'

type Verdict = 'correct' | 'deviation'

type CardSource = {
  label: string
  quote: string
  mark: 'amber' | 'sky'
}

type ReviewCard = {
  id: string
  title: string
  quote: string
  contrast: string
  basis: string
  pageNo: number | null
  regions: ClauseRegion[]
  sources: CardSource[]
  review: ReviewSpotLink | null
}

type ComparePane = {
  key: string
  document: StructureDocument
  pageNo: number
  quote: string
  label: string
  mark: 'amber' | 'sky'
  regions: ConflictBox[]
  locating: boolean
  linked: boolean
  emptyNote: string
  /** Nút cây đang chứa trích dẫn, để nối với thẩm định trích dẫn cùng vị trí. */
  clause: ClauseNode | null
  ordinal: number
  /**
   * Nút của cây `numbered` chứa trích dẫn. Màn tìm kiếm lưu thẩm định theo id nút
   * này, nên tra thẩm định trích dẫn phải dùng nó, không dùng cây theo
   * `structureMode` của hồ sơ.
   */
  reviewNode: ClauseNode | null
  reviewOrdinal: number
}

function paneRoleLabel(label: string) {
  const within = label.match(/Vế \d+/)
  if (within) return within[0]
  return label.startsWith('Xanh') ? 'Phụ lục' : 'Hợp đồng'
}

function linkedClausesOf(panes: ComparePane[]): LinkedClause[] {
  return panes.flatMap((pane) => {
    const node = pane.reviewNode ?? pane.clause
    if (!node) return []
    return [
      {
        label: paneRoleLabel(pane.label),
        documentId: pane.document.id,
        node,
        ordinal: pane.reviewNode ? pane.reviewOrdinal : pane.ordinal,
      },
    ]
  })
}

type KindFilter = 'all' | ConflictKind

const KIND_OPTIONS: { id: KindFilter; label: string; hint: string }[] = [
  { id: 'all', label: 'Tất cả', hint: 'Mọi xung đột trong hồ sơ.' },
  {
    id: 'between',
    label: 'Hợp đồng – Phụ lục',
    hint: 'Hai chỗ khác nhau nằm ở hai tài liệu: hợp đồng và phụ lục.',
  },
  {
    id: 'within',
    label: 'Trong cùng hợp đồng',
    hint: 'Hai chỗ mâu thuẫn nằm trong cùng một file hợp đồng.',
  },
]

const MARKS = ['amber', 'sky'] as const

function sourceLabel(label: string) {
  const normalized = label.trim().toLowerCase()
  if (normalized === 'contract' || normalized === 'a') return 'Hợp đồng'
  if (normalized === 'annex' || normalized === 'b') return 'Phụ lục'
  return label.trim() || 'Nguồn'
}

function sideQuote(side: { value: string; quote: string }) {
  const quote = side.quote.trim()
  if (quote) return quote
  const value = side.value.trim()
  return value && value !== '—' ? value : ''
}

function pageFromText(text: string) {
  const match = text.match(/trang\s+(\d+)/i)
  return match ? Number(match[1]) : null
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
  const texts = spot.sides.map(sideQuote).filter(Boolean)
  const within = withinDocumentId(spot) !== null
  const sources = spot.sides.flatMap((side, index) => {
    const quote = sideQuote(side)
    if (!quote) return []
    return [
      {
        label: within ? withinSideLabel(index) : sourceLabel(side.label),
        quote,
        mark: MARKS[index] ?? 'amber',
      },
    ]
  })
  const matched =
    linked ?? (texts[0] ? findClauseByQuote(nodes, texts[0], null) : null)
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
    regions: matched?.regions ?? [],
    sources,
    review: spot.review,
  }
}

const PANE_ROLES = [
  { role: 'contract', label: 'Vàng · Hợp đồng', mark: 'amber' },
  { role: 'annex', label: 'Xanh · Phụ lục', mark: 'sky' },
] as const

function documentByRole(documents: StructureDocument[], role: string) {
  return (
    documents.find((item) => item.role.toLowerCase() === role) ??
    (role === 'contract' ? documents[0] : null) ??
    null
  )
}

function passageOf(node: ClauseNode) {
  const head = headOf(node)
  const body = bodyOf(node)
  if (head && body) return `${head}. ${body}`
  return head || body || node.text
}

function linkPane(
  spot: ReviewSpot,
  document: StructureDocument,
  label: string,
  mark: 'amber' | 'sky',
  nodes: ClauseNode[],
  lines: OcrLine[] | undefined,
  numberedNodes: ClauseNode[],
  pick?: { side: ReviewSpotSide | null; key: string; missing: string },
): ComparePane {
  const side = pick
    ? pick.side
    : (spot.sides.find((item) => item.documentId === document.id) ?? null)
  const clause =
    lines && side
      ? clauseForCitation(nodes, lines, side.pageNo, side.lineNo)
      : null
  const reviewTarget = side
    ? reviewTargetNode(numberedNodes, lines ?? [], side)
    : null
  const fromTree = regionsOf(clause).map((region) => ({
    ...region,
    accent: mark,
  }))
  const fromCitation = (side?.regions ?? []).map((region) => ({
    ...region,
    accent: mark,
  }))
  const regions = fromTree.length > 0 ? fromTree : fromCitation
  const pageNo =
    (side?.pageNo && side.pageNo > 0 ? side.pageNo : null) ??
    regions.find((region) => region.pageNo > 0)?.pageNo ??
    (clause?.pageStart && clause.pageStart > 0 ? clause.pageStart : 1)
  const linked = Boolean(side && (clause || regions.length > 0 || side.pageNo))
  const quote = clause
    ? passageOf(clause)
    : linked
      ? sideQuote(side as ReviewSpotSide)
      : ''
  const missing =
    pick?.missing ??
    (label.startsWith('Xanh')
      ? 'Điểm này không có trích dẫn trên phụ lục.'
      : 'Điểm này không có trích dẫn trên hợp đồng.')
  return {
    key: pick?.key ?? document.id,
    document,
    pageNo,
    quote,
    label,
    mark,
    regions,
    locating:
      Boolean(side?.pageNo) && lines === undefined && regions.length === 0,
    linked,
    emptyNote: linked ? '' : missing,
    clause,
    ordinal: clause ? clauseOrdinal(nodes, clause.id) : 0,
    reviewNode: reviewTarget?.node ?? null,
    reviewOrdinal: reviewTarget?.ordinal ?? 0,
  }
}

function locatePanes(
  spot: ReviewSpot | null,
  documents: StructureDocument[],
  nodesByDocument: Record<string, ClauseNode[]>,
  linesByDocument: Record<string, OcrLine[] | undefined>,
  numberedByDocument: Record<string, ClauseNode[]>,
): ComparePane[] {
  if (!spot || documents.length === 0) return []
  const withinId = withinDocumentId(spot)
  const within = withinId
    ? (documents.find((item) => item.id === withinId) ?? null)
    : null
  if (within) {
    // Cả hai vế cùng một tài liệu: hai khung cùng file, mỗi khung một vế.
    const marks = [PANE_ROLES[0].mark, PANE_ROLES[1].mark] as const
    const colors = ['Vàng', 'Xanh'] as const
    return spot.sides.slice(0, 2).map((side, index) =>
      linkPane(
        spot,
        within,
        `${colors[index]} · ${withinSideLabel(index)}`,
        marks[index],
        nodesByDocument[within.id] ?? [],
        linesByDocument[within.id],
        numberedByDocument[within.id] ?? [],
        {
          side,
          key: `${within.id}:${index}`,
          missing: `Điểm này không có trích dẫn ở ${withinSideLabel(index).toLowerCase()}.`,
        },
      ),
    )
  }
  const contract = documentByRole(documents, 'contract')
  const annex =
    documentByRole(documents, 'annex') ??
    documents.find((item) => item.id !== contract?.id) ??
    null
  const pair = [
    contract
      ? linkPane(
          spot,
          contract,
          PANE_ROLES[0].label,
          PANE_ROLES[0].mark,
          nodesByDocument[contract.id] ?? [],
          linesByDocument[contract.id],
          numberedByDocument[contract.id] ?? [],
        )
      : null,
    annex
      ? linkPane(
          spot,
          annex,
          PANE_ROLES[1].label,
          PANE_ROLES[1].mark,
          nodesByDocument[annex.id] ?? [],
          linesByDocument[annex.id],
          numberedByDocument[annex.id] ?? [],
        )
      : null,
  ].filter((pane): pane is ComparePane => pane !== null)
  return pair
}

function demoCards(): ReviewCard[] {
  return clauseConflicts.map((conflict) => {
    const quote =
      `${conflict.source1.quoteBefore}${conflict.source1.highlight}${conflict.source1.quoteAfter}`.trim()
    const contrast =
      `${conflict.source2.quoteBefore}${conflict.source2.highlight}${conflict.source2.quoteAfter}`.trim()
    const pageNo =
      pageFromText(conflict.source1.location) ?? pageFromText(conflict.location)
    return {
      id: conflict.id,
      title: conflict.title,
      quote,
      contrast,
      basis: basisOf('', pageNo, 0),
      pageNo,
      regions: [],
      sources: [
        { label: 'Nguồn 1', quote, mark: 'amber' },
        ...(contrast
          ? [
              {
                label: 'Nguồn 2' as const,
                quote: contrast,
                mark: 'sky' as const,
              },
            ]
          : []),
      ],
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
      <MaterialIcon
        name={icon}
        className={`text-[14px] ${active ? '' : iconClass}`}
      />
      <span>{label}</span>
    </button>
  )
}

export function ClauseConflictPage() {
  usePageTitle('Đối soát xung đột')
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const reviewState = location.state as {
    dossierId?: string
    name?: string
    findingId?: string
  } | null
  const dossierId = reviewState?.dossierId ?? searchParams.get('dossier') ?? ''
  // Từ cây / banner nhảy sang: mở đúng xung đột đó và cuộn thẻ vào tầm nhìn.
  const requestedId =
    searchParams.get('finding') ?? reviewState?.findingId ?? ''
  const { user } = useAuth()
  const searchRef = useRef<HTMLInputElement>(null)
  const loadedLines = useRef(new Set<string>())
  const scrolledTo = useRef('')
  const [detail, setDetail] = useState<DossierStructure | null>(null)
  const [document, setDocument] = useState<StructureDocument | null>(null)
  const [spots, setSpots] = useState<ReviewSpot[]>([])
  const [nodesByDocument, setNodesByDocument] = useState<
    Record<string, ClauseNode[]>
  >({})
  const [linesByDocument, setLinesByDocument] = useState<
    Record<string, OcrLine[]>
  >({})
  const [pdfPages, setPdfPages] = useState(0)
  const [loading, setLoading] = useState(Boolean(dossierId))
  const [error, setError] = useState<string | null>(null)
  const [activeId, setActiveId] = useState(requestedId)
  const [pageNo, setPageNo] = useState(1)
  const [align, setAlign] = useState<{
    mark: 'amber' | 'sky' | 'both'
    tick: number
  }>({ mark: 'both', tick: 0 })
  const [query, setQuery] = useState('')
  const [reviewedIds, setReviewedIds] = useState<Record<string, boolean>>({})
  const [kind, setKind] = useState<KindFilter>('all')
  const [verdicts, setVerdicts] = useState<Record<string, Verdict>>({})
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
    setLinesByDocument({})
    setNodesByDocument({})
    loadedLines.current.clear()
    Promise.all([
      getDossierStructure(dossierId, controller.signal),
      listReviewSpots(dossierId, controller.signal),
    ])
      .then(async ([nextDetail, nextSpots]) => {
        if (controller.signal.aborted) return
        setDetail(nextDetail)
        const nextDocument = contractDocument(nextDetail)
        setDocument(nextDocument)
        const trees = await Promise.all(
          nextDetail.documents.map(async (item) => {
            try {
              const tree = await listClauses(item.id, controller.signal)
              return [item.id, tree] as const
            } catch {
              return [item.id, [] as ClauseNode[]] as const
            }
          }),
        )
        if (controller.signal.aborted) return
        setNodesByDocument(Object.fromEntries(trees))
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

  const contractId = useMemo(
    () => (detail ? (contractDocument(detail)?.id ?? null) : null),
    [detail],
  )
  const nodes = nodesByDocument[contractId ?? ''] ?? []
  const pageCount = document?.pageCount || pdfPages
  const cards = useMemo(() => {
    if (!dossierId) return demoCards()
    return spots.map((spot) => spotToCard(spot, nodes, pageCount))
  }, [dossierId, nodes, pageCount, spots])

  const kindById = useMemo(() => {
    const map = new Map<string, ConflictKind>()
    for (const spot of spots) map.set(spot.id, conflictKind(spot))
    return map
  }, [spots])
  const kindCounts = useMemo(() => {
    const counts = { between: 0, within: 0 }
    for (const card of cards) {
      const value = kindById.get(card.id)
      if (value) counts[value] += 1
    }
    return counts
  }, [cards, kindById])
  // Chỉ hiện bộ lọc khi hồ sơ có cả hai loại, tránh gây rối khi chỉ có một.
  const showKinds = kindCounts.between > 0 && kindCounts.within > 0
  const inKind = useMemo(
    () =>
      kind === 'all' || !showKinds
        ? cards
        : cards.filter((card) => kindById.get(card.id) === kind),
    [cards, kind, kindById, showKinds],
  )

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return inKind
    return inKind.filter((card) =>
      `${card.title} ${card.quote} ${card.basis}`.toLowerCase().includes(term),
    )
  }, [inKind, query])

  const structureMode = detail?.structureMode ?? 'numbered'
  const trees = useMemo(() => {
    const map: Record<string, ClauseNode[]> = {}
    for (const [id, lines] of Object.entries(linesByDocument)) {
      map[id] =
        lines.length > 0
          ? buildStructureTree(lines, structureMode)
          : (nodesByDocument[id] ?? [])
    }
    return map
  }, [linesByDocument, nodesByDocument, structureMode])
  // Màn tìm kiếm lưu thẩm định theo id nút của cây numbered.
  const numberedTrees = useMemo(() => {
    const map: Record<string, ClauseNode[]> = {}
    for (const [id, lines] of Object.entries(linesByDocument)) {
      map[id] =
        lines.length > 0
          ? buildStructureTree(lines, 'numbered')
          : (nodesByDocument[id] ?? [])
    }
    return map
  }, [linesByDocument, nodesByDocument])
  const active =
    inKind.find((card) => card.id === activeId) ??
    visible[0] ??
    inKind[0] ??
    cards[0] ??
    null
  const linksById = useMemo(() => {
    const map = new Map<string, ComparePane[]>()
    const documents = detail?.documents ?? []
    for (const spot of spots) {
      map.set(
        spot.id,
        locatePanes(spot, documents, trees, linesByDocument, numberedTrees),
      )
    }
    return map
  }, [detail?.documents, linesByDocument, numberedTrees, spots, trees])
  const located = linksById.get(active?.id ?? '') ?? []
  const comparing = located.length > 1

  useEffect(() => {
    if (!active?.id) return
    setAlign({ mark: 'both', tick: Date.now() })
  }, [active?.id])

  useEffect(() => {
    if (inKind.length === 0) return
    if (!inKind.some((card) => card.id === activeId)) setActiveId(inKind[0].id)
  }, [activeId, inKind])

  useEffect(() => {
    if (!requestedId || scrolledTo.current === requestedId) return
    if (!cards.some((card) => card.id === requestedId)) return
    scrolledTo.current = requestedId
    // Đi tới từ chấm xung đột trên cây: nếu bộ lọc đang ẩn thẻ này thì bỏ lọc.
    setKind('all')
    setActiveId(requestedId)
    const frame = window.requestAnimationFrame(() => {
      window.document
        .querySelector(`[data-card-id="${CSS.escape(requestedId)}"]`)
        ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [cards, requestedId])

  useEffect(() => {
    const documents = detail?.documents ?? []
    const pending = documents.filter(
      (item) => !loadedLines.current.has(item.id),
    )
    if (pending.length === 0) return
    const controller = new AbortController()
    for (const item of pending) {
      loadedLines.current.add(item.id)
      loadDocumentLines(item.id, controller.signal)
        .then((lines) => {
          if (controller.signal.aborted) return
          setLinesByDocument((current) => ({ ...current, [item.id]: lines }))
        })
        .catch(() => {
          if (controller.signal.aborted) {
            loadedLines.current.delete(item.id)
            return
          }
          setLinesByDocument((current) => ({ ...current, [item.id]: [] }))
        })
    }
    return () => controller.abort()
  }, [detail?.documents])

  const focusKey =
    located.length === 1
      ? `${active?.id ?? ''}:${located[0].document.id}:${located[0].pageNo}`
      : ''

  useEffect(() => {
    if (located.length !== 1 || !focusKey) return
    setDocument(located[0].document)
    setPageNo(located[0].pageNo)
  }, [focusKey, located])

  function selectDocument(id: string) {
    const next = detail?.documents.find((item) => item.id === id) ?? null
    if (!next || next.id === document?.id) return
    setDocument(next)
    setPdfPages(0)
    setPageNo(1)
  }

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
  const ignorePageCount = useCallback(() => undefined, [])
  const onPageChange = useCallback((page: number) => {
    setPageNo(Math.max(1, page))
  }, [])

  const reviewed = cards.filter((card) =>
    dossierId ? reviewedIds[card.id] : verdicts[card.id],
  ).length
  const dossierName =
    detail?.name?.trim() || reviewState?.name?.trim() || 'Hồ sơ hợp đồng'

  function choose(id: string, verdict: Verdict) {
    setVerdicts((current) => ({ ...current, [id]: verdict }))
  }

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col">
      <section className="mb-space-sm w-full shrink-0 border-b border-outline-variant/40 bg-surface-container-lowest px-gutter py-space-sm">
        <div className="flex flex-wrap items-center justify-between gap-space-sm">
          <div className="flex flex-wrap items-center gap-space-md">
            <div className="flex items-center gap-space-xs font-label-md text-label-md text-secondary">
              <span>Hồ sơ Hợp đồng</span>
              <span className="text-outline-variant">/</span>
              <span className="font-semibold text-on-surface">
                {dossierName}
              </span>
            </div>
            {comparing ? (
              <div className="hidden items-center gap-space-sm font-label-sm text-label-sm text-secondary lg:flex">
                <span className="font-medium text-on-surface">
                  Đối chiếu {located.length} tài liệu
                </span>
              </div>
            ) : document ? (
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

      {dossierId ? (
        <details className="max-h-[60vh] overflow-auto rounded border border-outline-variant/40 p-2">
          <summary className="cursor-pointer font-semibold">
            Điều khoản, cặp nghi vấn và dòng thời gian
          </summary>
          <ClauseFrameResults
            dossierId={dossierId}
            expectedRun={spots.find((spot) => spot.runId)?.runId ?? undefined}
          />
        </details>
      ) : null}

      <div className="grid min-h-0 w-full flex-1 grid-cols-1 overflow-hidden rounded border border-outline-variant/50 bg-surface-container-low shadow-sm max-xl:grid-rows-[minmax(420px,1fr)_minmax(420px,1fr)] max-xl:overflow-y-auto xl:grid-cols-12">
        <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden border-r border-outline-variant/60 xl:col-span-7">
          {comparing ? (
            <div className="grid h-full min-h-0 flex-1 grid-rows-2">
              {located.map((pane, index) => (
                <div
                  key={pane.key}
                  className="flex h-full min-h-0 flex-col overflow-hidden border-b border-outline-variant/50 last:border-b-0"
                >
                  <ConflictDocumentPane
                    alignToken={
                      align.mark === 'both' || align.mark === pane.mark
                        ? align.tick
                        : 0
                    }
                    citeNo={
                      index === 0 && active
                        ? cards.findIndex((card) => card.id === active.id) + 1
                        : null
                    }
                    documentId={pane.document.id}
                    filename={pane.document.filename}
                    emptyNote={pane.emptyNote}
                    locating={pane.locating}
                    locked
                    mark={pane.mark}
                    pageCount={pane.document.pageCount}
                    pageNo={pane.pageNo}
                    quote={pane.quote}
                    regions={pane.regions}
                    sourceLabel={pane.label}
                    title={active?.title ?? ''}
                    onBack={index === 0 ? () => navigate(backTo) : undefined}
                    onPageChange={onPageChange}
                    onPageCount={index === 0 ? onPageCount : ignorePageCount}
                  />
                </div>
              ))}
            </div>
          ) : (
            <ConflictDocumentPane
              citeNo={
                active
                  ? cards.findIndex((card) => card.id === active.id) + 1
                  : null
              }
              documentId={document?.id ?? null}
              filename={document?.filename ?? ''}
              files={detail?.documents ?? []}
              locating={
                located.find((pane) => pane.document.id === document?.id)
                  ?.locating ?? false
              }
              pageCount={pageCount}
              pageNo={pageNo}
              quote={active?.quote ?? ''}
              regions={
                located.find((pane) => pane.document.id === document?.id)
                  ?.regions ??
                (document?.id === contractId ? (active?.regions ?? []) : [])
              }
              title={active?.title ?? ''}
              onBack={() => navigate(backTo)}
              onPageChange={onPageChange}
              onPageCount={onPageCount}
              onSelectDocument={selectDocument}
            />
          )}
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
              {comparing ? (
                <span className="flex items-center gap-2 font-label-sm text-label-sm text-secondary">
                  {located.map((pane) => (
                    <span
                      key={pane.key}
                      className="inline-flex items-center gap-1"
                    >
                      <span
                        className={`h-2 w-2 rounded-sm ${
                          pane.mark === 'sky' ? 'bg-sky-500' : 'bg-amber-500'
                        }`}
                      />
                      {pane.label}
                    </span>
                  ))}
                </span>
              ) : null}
            </div>
            {showKinds ? (
              <div>
                <div
                  aria-label="Loại xung đột"
                  className="flex flex-wrap gap-1"
                  role="group"
                >
                  {KIND_OPTIONS.map((option) => {
                    const count =
                      option.id === 'all' ? cards.length : kindCounts[option.id]
                    const on = kind === option.id
                    return (
                      <button
                        key={option.id}
                        aria-pressed={on}
                        className={`rounded px-2.5 py-1 font-label-sm text-label-sm transition-colors ${
                          on
                            ? 'bg-primary-container font-semibold text-on-primary'
                            : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'
                        }`}
                        type="button"
                        onClick={() => setKind(option.id)}
                      >
                        {option.label} · {count}
                      </button>
                    )
                  })}
                </div>
                <p className="mt-1 font-label-sm text-label-sm text-secondary">
                  {KIND_OPTIONS.find((option) => option.id === kind)?.hint}
                </p>
              </div>
            ) : null}
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
              <div aria-live="polite" className="space-y-space-sm">
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Đang tải các chỗ cần kiểm tra…
                </p>
                <div aria-hidden="true" className="space-y-space-sm">
                  {Array.from({ length: 6 }, (_, index) => (
                    <div
                      key={index}
                      className="h-28 animate-pulse rounded border border-outline-variant/30 bg-surface-container-low"
                    />
                  ))}
                </div>
              </div>
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
                  Hồ sơ này không có chỗ cần chọn nguồn. Các chỗ cần xử lý, nếu
                  có, nằm trên cây cấu trúc.
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
                  data-card-id={card.id}
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
                          selected
                            ? 'text-primary-container'
                            : 'text-on-surface'
                        }`}
                      >
                        {card.title}
                      </span>
                    </button>
                    {selected ? (
                      <span className="inline-flex items-center gap-1 rounded bg-primary-container px-1.5 py-0.5 font-label-sm text-[10px] font-semibold uppercase text-on-primary">
                        <MaterialIcon
                          name="visibility"
                          className="text-[12px]"
                        />
                        Đang xem trên PDF
                      </span>
                    ) : card.pageNo ? (
                      <button
                        className="flex items-center gap-0.5 font-label-sm text-label-sm text-secondary hover:text-primary-container"
                        type="button"
                        onClick={() => setActiveId(card.id)}
                      >
                        <span>Đến trang {card.pageNo}</span>
                        <MaterialIcon
                          name="arrow_forward"
                          className="text-[14px]"
                        />
                      </button>
                    ) : null}
                  </div>
                  {(linksById.get(card.id)?.length ?? 0) > 1 ? (
                    <div className="mb-space-sm space-y-1.5">
                      <p className="font-body-sm text-body-sm leading-normal text-on-surface-variant">
                        {card.quote}
                      </p>
                      {linksById.get(card.id)?.map((pane) => (
                        <button
                          key={pane.key}
                          className={`w-full rounded border border-l-4 p-2 text-left font-body-sm text-body-sm leading-normal ${
                            pane.mark === 'sky'
                              ? 'border-sky-200 border-l-sky-600 bg-sky-50/80 hover:bg-sky-100'
                              : 'border-amber-200 border-l-amber-500 bg-amber-50/80 hover:bg-amber-100'
                          } ${selected ? 'text-on-surface' : 'text-on-surface-variant'}`}
                          type="button"
                          onClick={() => {
                            setActiveId(card.id)
                            setAlign({ mark: pane.mark, tick: Date.now() })
                          }}
                        >
                          <span className="mb-0.5 block font-label-sm font-semibold text-on-surface">
                            {pane.label}
                            {pane.linked && pane.pageNo > 0
                              ? ` · Trang ${pane.pageNo}`
                              : ''}
                          </span>
                          {pane.locating
                            ? 'Đang nối với cây cấu trúc…'
                            : pane.linked
                              ? `“${pane.quote}”`
                              : pane.emptyNote}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <>
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
                    </>
                  )}
                  <div className="mb-space-sm flex flex-wrap items-center justify-between gap-space-xs border-t border-outline-variant/30 pt-space-xs font-label-sm text-label-sm text-secondary">
                    <span className="font-code-sm text-code-sm font-medium text-on-surface-variant">
                      {card.basis}
                    </span>
                  </div>
                  {dossierId ? (
                    <ConflictFindingReview
                      findingId={card.id}
                      semantic={
                        spots.find((spot) => spot.id === card.id)?.semantic
                      }
                      linkedClauses={linkedClausesOf(
                        linksById.get(card.id) ?? [],
                      )}
                      onReviewed={(value) =>
                        setReviewedIds((current) =>
                          current[card.id] === value
                            ? current
                            : { ...current, [card.id]: value },
                        )
                      }
                    />
                  ) : (
                    <div className="grid grid-cols-2 gap-1.5">
                      <VerdictButton
                        active={verdict === 'correct'}
                        icon="check"
                        iconClass="text-tertiary-container"
                        label="Đúng"
                        onClick={() => choose(card.id, 'correct')}
                      />
                      <VerdictButton
                        active={verdict === 'deviation'}
                        icon="close"
                        iconClass="text-error"
                        label="Sai"
                        onClick={() => choose(card.id, 'deviation')}
                      />
                    </div>
                  )}
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
    </div>
  )
}
