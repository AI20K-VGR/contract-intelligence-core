import { useCallback, useEffect, useRef, useState } from 'react'
import { relationLabel, reviewStateLabel } from '../../structure/displayLabels'
import {
  getContractGraphPage,
  type ContractGraphEdge,
  type ContractGraphKind,
  type ContractGraphPage,
  type ContractGraphStatus,
  type ProcessingTrace,
} from '../../api/contractGraph'
import { MaterialIcon } from '../icons'
import { loadAi2GraphDataIfVisible } from './contractGraphRuntime'
import { graphStatusLabel } from './contractGraphViewModel'
import { AnalysisNotices, AnalysisStatus } from './ProcessingTimeline'
import { RelationInspector } from './RelationInspector'
import { RelationList } from './RelationList'
import {
  RELATION_TONES,
  relationDotClasses,
  relationFillClasses,
  relationStrokeClasses,
  relationTone,
  type RelationTone,
} from './relationTone'

type NodeLabelResolver = (nodeId: string, documentId?: string | null) => string

type GraphView = 'diagram' | 'list'

const GRAPH_VIEW_KEY = 'ai2_graph_view'

function readGraphView(): GraphView {
  try {
    return window.localStorage.getItem(GRAPH_VIEW_KEY) === 'list'
      ? 'list'
      : 'diagram'
  } catch {
    return 'diagram'
  }
}

export function Ai2GraphDossierView({
  enabled,
  dossierId,
  jobId,
  snapshotDigest,
  graphKind,
  resolveNodeLabel,
  resolveNodeTitle,
  onOpenCitation,
  onSelectRelation,
  onResolveEdgeEvidence,
  citationRecord,
  citationError,
  citationLoading,
}: {
  enabled: boolean
  dossierId: string
  jobId: string
  snapshotDigest: string
  graphKind: ContractGraphKind
  resolveNodeLabel: NodeLabelResolver
  /** Tên ngắn của điều khoản (số điều, tên tệp) để đặt trên nút sơ đồ. */
  resolveNodeTitle?: NodeLabelResolver
  onOpenCitation: (citationRef: string, nodeId: string) => void
  onSelectRelation: (edgeId: string) => void
  onResolveEdgeEvidence?: (edge: ContractGraphEdge) => Promise<{
    sourceText?: string
    targetText?: string
  } | null>
  citationRecord?: Record<string, unknown> | null
  citationError?: boolean
  citationLoading?: boolean
}) {
  const [data, setData] = useState<{
    page: ContractGraphPage | null
    trace: ProcessingTrace
    graphError: boolean
  } | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  const [view, setView] = useState<GraphView>(readGraphView)
  const [filter, setFilter] = useState<string | null>(null)
  const [resolvedEvidence, setResolvedEvidence] = useState<
    Record<string, string>
  >({})
  const resolveEdgeEvidenceRef = useRef(onResolveEdgeEvidence)
  const evidenceRequests = useRef(
    new Map<
      string,
      Promise<{
        sourceText?: string
        targetText?: string
      } | null>
    >(),
  )
  resolveEdgeEvidenceRef.current = onResolveEdgeEvidence
  const load = useCallback(
    async (signal: AbortSignal) => {
      const result = await loadAi2GraphDataIfVisible({
        enabled,
        visible: true,
        dossierId,
        jobId,
        snapshotDigest,
        graphKind,
        signal,
      })
      return result
    },
    [dossierId, enabled, graphKind, jobId, snapshotDigest],
  )

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    setLoading(true)
    setError(false)
    setData(null)
    setSelectedId(null)
    setFilter(null)
    setResolvedEvidence({})
    load(controller.signal)
      .then((result) => {
        if (cancelled || !result) return
        setData(result)
        setSelectedId(result.page?.edges[0]?.id ?? null)
      })
      .catch(() => {
        if (!cancelled && !controller.signal.aborted) setError(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [load, retry])

  const resolveAndStoreEdgeEvidence = useCallback((edge: ContractGraphEdge) => {
    const pending = evidenceRequests.current.get(edge.id)
    if (pending) return pending
    const resolver = resolveEdgeEvidenceRef.current
    if (!resolver) return Promise.resolve(null)
    const request = resolver(edge)
      .then((evidence) => {
        if (evidence) {
          setResolvedEvidence((current) => ({
            ...current,
            ...(evidence.sourceText && edge.source_document_id
              ? {
                  [`${edge.source_document_id}\u0000${edge.source_node_id}`]:
                    evidence.sourceText,
                }
              : {}),
            ...(evidence.targetText && edge.target_document_id
              ? {
                  [`${edge.target_document_id}\u0000${edge.target_node_id}`]:
                    evidence.targetText,
                }
              : {}),
          }))
        }
        return evidence
      })
      .finally(() => {
        evidenceRequests.current.delete(edge.id)
      })
    evidenceRequests.current.set(edge.id, request)
    return request
  }, [])

  useEffect(() => {
    const edges = data?.page?.edges ?? []
    if (!resolveEdgeEvidenceRef.current || edges.length === 0) return
    void (async () => {
      for (let start = 0; start < edges.length; start += 3) {
        await Promise.all(
          edges
            .slice(start, start + 3)
            .map((edge) => resolveAndStoreEdgeEvidence(edge)),
        )
      }
    })()
  }, [data?.page, resolveAndStoreEdgeEvidence])

  const resolveVisibleNodeLabel = useCallback(
    (nodeId: string, documentId?: string | null) =>
      (documentId
        ? resolvedEvidence[`${documentId}\u0000${nodeId}`]
        : undefined) || resolveNodeLabel(nodeId, documentId),
    [resolveNodeLabel, resolvedEvidence],
  )

  const loadNextPage = useCallback(
    (cursor: string) =>
      getContractGraphPage({
        dossierId,
        jobId,
        snapshotDigest,
        graphKind,
        cursor,
      }),
    [dossierId, graphKind, jobId, snapshotDigest],
  )
  const selectRelation = useCallback(
    (edgeId: string) => {
      setSelectedId(edgeId)
      onSelectRelation(edgeId)
    },
    [onSelectRelation],
  )

  function changeView(next: GraphView) {
    setView(next)
    try {
      window.localStorage.setItem(GRAPH_VIEW_KEY, next)
    } catch {
      // Không lưu được thì lần sau mở lại kiểu mặc định.
    }
  }

  function changeFilter(next: string | null) {
    setFilter(next)
    // Quan hệ đang chọn bị lọc mất thì chọn quan hệ đầu tiên còn hiện.
    const edges = data?.page?.edges ?? []
    const selected = edges.find((edge) => edge.id === selectedId)
    if (next && selected && relationLabel(selected.label) !== next) {
      const first = edges.find((edge) => relationLabel(edge.label) === next)
      if (first) selectRelation(first.id)
    }
  }

  if (loading)
    return (
      <p
        className="flex items-center gap-space-sm rounded-lg bg-surface-container-lowest p-space-lg font-body-sm text-body-sm text-on-surface-variant shadow-sm"
        role="status"
      >
        <MaterialIcon
          name="progress_activity"
          className="animate-spin text-[20px] text-primary"
        />
        Đang tải sơ đồ quan hệ…
      </p>
    )
  if (error || !data)
    return (
      <GraphLoadError
        message="Không tải được sơ đồ quan hệ. Vui lòng thử lại sau ít phút."
        retryLabel="Thử tải lại"
        onRetry={() => setRetry((value) => value + 1)}
      />
    )
  const page = data.page
  // Không có quan hệ nào để vẽ (dù READY hay bước bị bỏ qua, lỗi lưu…): chỉ
  // báo trống, không hiện bộ lọc, kiểu xem hay khung chi tiết.
  const nothingFound =
    page !== null && page.edges.length === 0 && !page.has_more
  const selectedEdge =
    page?.edges.find((edge) => edge.id === selectedId) ?? null
  const showResults = !data.graphError && page !== null && !nothingFound
  return (
    <section
      aria-label={
        graphKind === 'operation' ? 'Sửa đổi điều khoản' : 'Quan hệ điều khoản'
      }
      className="flex min-w-0 flex-col gap-space-md rounded-lg bg-surface-container-lowest p-space-lg shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        {showResults ? (
          <RelationFilter page={page} value={filter} onChange={changeFilter} />
        ) : (
          <span />
        )}
        <div className="flex items-center gap-space-sm">
          <AnalysisStatus trace={data.trace} graphKind={graphKind} />
          {showResults ? (
            <ViewSwitch value={view} onChange={changeView} />
          ) : null}
        </div>
      </div>
      <AnalysisNotices trace={data.trace} graphKind={graphKind} />
      {data.graphError || !page ? (
        <GraphLoadError
          message="Không tải được sơ đồ quan hệ."
          retryLabel="Tải lại sơ đồ"
          onRetry={() => setRetry((value) => value + 1)}
        />
      ) : nothingFound ? (
        <EmptyGraph kind={graphKind} status={page.status} />
      ) : view === 'diagram' ? (
        <div className="grid min-w-0 items-start gap-gutter lg:grid-cols-[minmax(0,1fr)_340px] 2xl:grid-cols-[minmax(0,1fr)_400px]">
          <ContractGraphCanvas
            page={page}
            filter={filter}
            selectedId={selectedId}
            onSelectEdge={selectRelation}
            resolveNodeLabel={resolveVisibleNodeLabel}
            resolveNodeTitle={resolveNodeTitle}
          />
          <div className="min-w-0 lg:sticky lg:top-0">
            {selectedEdge ? (
              <RelationInspector
                edge={selectedEdge}
                onOpenCitation={onOpenCitation}
                resolveNodeLabel={resolveVisibleNodeLabel}
                resolveNodeTitle={resolveNodeTitle}
                citationRecord={citationRecord}
                citationError={citationError}
                citationLoading={citationLoading}
              />
            ) : (
              <InspectorPlaceholder />
            )}
          </div>
        </div>
      ) : (
        <RelationList
          key={`${jobId}:${snapshotDigest}:${graphKind}`}
          page={page}
          filter={filter}
          onLoadPage={loadNextPage}
          onOpenCitation={onOpenCitation}
          onResolveEdgeEvidence={resolveAndStoreEdgeEvidence}
          onSelectEdge={selectRelation}
          resolveNodeLabel={resolveVisibleNodeLabel}
          resolveNodeTitle={resolveNodeTitle}
          citationRecord={citationRecord}
          citationError={citationError}
          citationLoading={citationLoading}
          selectedId={selectedId}
        />
      )}
    </section>
  )
}

/** Chú thích màu của từng loại quan hệ, bấm để chỉ xem loại đó. */
function RelationFilter({
  page,
  value,
  onChange,
}: {
  page: ContractGraphPage
  value: string | null
  onChange: (next: string | null) => void
}) {
  const groups = new Map<string, { tone: RelationTone; count: number }>()
  for (const edge of page.edges) {
    const label = relationLabel(edge.label)
    const group = groups.get(label)
    if (group) group.count += 1
    else groups.set(label, { tone: relationTone(edge.label), count: 1 })
  }
  // Còn trang chưa tải thì số theo loại chưa đúng, chỉ hiện tổng.
  const exact = !page.has_more
  const chip = (active: boolean) =>
    `inline-flex h-8 items-center gap-space-xs rounded-full px-space-md font-body-sm text-body-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 ${
      active
        ? 'bg-brand-100 text-brand-700 shadow-sm ring-1 ring-brand-200'
        : 'text-on-surface-variant hover:bg-surface-container-high hover:text-primary'
    }`
  return (
    <div
      className="flex min-w-0 flex-wrap items-center gap-0.5 rounded-full bg-surface-container p-1"
      role="group"
      aria-label="Lọc theo loại quan hệ"
    >
      <button
        aria-pressed={value === null}
        className={chip(value === null)}
        onClick={() => onChange(null)}
        type="button"
      >
        Tất cả
        <span className="tabular-nums opacity-70">{page.total_count}</span>
      </button>
      {[...groups]
        .sort(
          ([, a], [, b]) =>
            RELATION_TONES.indexOf(a.tone) - RELATION_TONES.indexOf(b.tone),
        )
        .map(([label, group]) => (
          <button
            key={label}
            aria-pressed={value === label}
            className={chip(value === label)}
            onClick={() => onChange(value === label ? null : label)}
            type="button"
          >
            <span
              aria-hidden
              className={`h-2 w-2 rounded-full ${relationDotClasses[group.tone]}`}
            />
            {label}
            {exact ? (
              <span className="tabular-nums opacity-70">{group.count}</span>
            ) : null}
          </button>
        ))}
    </div>
  )
}

function ViewSwitch({
  value,
  onChange,
}: {
  value: GraphView
  onChange: (next: GraphView) => void
}) {
  return (
    <div
      className="inline-flex items-center gap-0.5 rounded-full bg-surface-container p-1"
      role="group"
      aria-label="Kiểu xem"
    >
      {(
        [
          ['diagram', 'hub', 'Sơ đồ'],
          ['list', 'view_list', 'Danh sách'],
        ] as const
      ).map(([id, icon, label]) => (
        <button
          key={id}
          aria-pressed={value === id}
          className={`inline-flex h-8 items-center gap-space-xs rounded-full px-space-sm font-body-sm text-body-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 ${
            value === id
              ? 'bg-brand-100 text-brand-700 shadow-sm ring-1 ring-brand-200'
              : 'text-on-surface-variant hover:bg-surface-container-high hover:text-primary'
          }`}
          onClick={() => onChange(id)}
          title={label}
          type="button"
        >
          <MaterialIcon name={icon} className="text-[18px]" />
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  )
}

function InspectorPlaceholder() {
  return (
    <div className="flex flex-col items-center gap-space-xs rounded-lg bg-surface-container-low px-space-lg py-space-xl text-center font-body-sm text-body-sm text-on-surface-variant">
      <MaterialIcon name="ads_click" className="text-[28px] text-outline" />
      Chọn một đường nối trên sơ đồ để xem hai điều khoản liên quan.
    </div>
  )
}

function EmptyGraph({
  kind,
  status = 'READY',
}: {
  kind: ContractGraphKind
  status?: ContractGraphStatus
}) {
  // READY và SKIPPED đã được chip trạng thái và lời giải thích phía trên nói rõ;
  // trạng thái lỗi lưu, chưa sẵn sàng… thì ghi thêm một dòng.
  const note =
    status === 'READY' || status === 'SKIPPED' ? null : graphStatusLabel(status)
  return (
    <div
      className="flex flex-col items-center gap-space-xs rounded-lg bg-surface-container-low px-space-lg py-space-xl text-center"
      role="status"
    >
      <MaterialIcon name="account_tree" className="text-[32px] text-outline" />
      <p className="font-body-sm text-body-sm font-semibold text-on-surface">
        {kind === 'operation'
          ? 'Chưa tìm thấy điều khoản nào bị sửa đổi'
          : 'Chưa tìm thấy quan hệ nào giữa các điều khoản'}
      </p>
      {note ? (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          {note}
        </p>
      ) : null}
    </div>
  )
}

function GraphLoadError({
  message,
  retryLabel,
  onRetry,
}: {
  message: string
  retryLabel: string
  onRetry: () => void
}) {
  return (
    <div
      role="alert"
      className="flex min-w-0 flex-wrap items-center gap-space-sm rounded-lg bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container"
    >
      <MaterialIcon name="error" className="text-[18px]" />
      <span className="min-w-0 flex-1">{message}</span>
      <button
        className="shrink-0 font-semibold text-primary hover:underline"
        onClick={onRetry}
        type="button"
      >
        {retryLabel}
      </button>
    </div>
  )
}

const ZOOM_BUTTON =
  'inline-flex h-8 w-8 items-center justify-center rounded-full text-on-surface hover:bg-surface-container-high focus-visible:outline focus-visible:outline-2'

const MIN_ZOOM = 0.5
const MAX_ZOOM = 2.5

function clampZoom(value: number) {
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.round(value * 10) / 10))
}

// Kích thước sơ đồ (đơn vị viewBox): hai cột điều khoản, đường nối ở giữa.
const WIDTH = 960
const NODE_W = 272
const NODE_H = 76
const ROW = 96
const PAD = 24
const COLUMN_X = { left: PAD, right: WIDTH - PAD - NODE_W } as const

type GraphNode = {
  key: string
  label: string
  title: string
  column: 'left' | 'right'
  x: number
  y: number
}

export function ContractGraphCanvas({
  page,
  selectedId,
  onSelectEdge,
  filter = null,
  resolveNodeLabel = (nodeId) => `Mã điều khoản ${nodeId}`,
  resolveNodeTitle,
}: {
  page: ContractGraphPage
  selectedId: string | null
  onSelectEdge: (edgeId: string) => void
  /** Chỉ vẽ loại quan hệ này (tên hiển thị); null là vẽ tất cả. */
  filter?: string | null
  resolveNodeLabel?: NodeLabelResolver
  resolveNodeTitle?: NodeLabelResolver
}) {
  const [zoom, setZoom] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [focus, setFocus] = useState<string | null>(null)
  const drag = useRef<{
    pointerId: number
    x: number
    y: number
  } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  // Lăn chuột thường để cuộn trang; giữ Ctrl (⌘) mới phóng to. Gắn trực tiếp
  // vì onWheel của React là passive, không chặn được trang cùng cuộn.
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) return
      event.preventDefault()
      setZoom((value) => clampZoom(value + (event.deltaY < 0 ? 0.1 : -0.1)))
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }, [page.edges.length])

  const edges = filter
    ? page.edges.filter((edge) => relationLabel(edge.label) === filter)
    : page.edges
  const nodes = layoutNodes(edges, resolveNodeLabel, resolveNodeTitle)
  const rows = edges.map((edge) => {
    const source = nodes.get(
      nodeKey(
        edge.source_node_id,
        edge.source_document_id,
        `${edge.id}:source`,
      ),
    )!
    const target = nodes.get(
      nodeKey(
        edge.target_node_id,
        edge.target_document_id,
        `${edge.id}:target`,
      ),
    )!
    return { edge, source, target, ...edgeGeometry(source, target) }
  })
  const columnSize = (column: 'left' | 'right') =>
    [...nodes.values()].filter((node) => node.column === column).length
  const height =
    PAD * 2 +
    Math.max(1, columnSize('left'), columnSize('right')) * ROW -
    (ROW - NODE_H)
  const selected = rows.find((row) => row.edge.id === selectedId)
  // Đang trỏ vào một đường nối hay một điều khoản thì làm mờ phần không liên quan.
  const focusedRows = focus
    ? rows.filter(
        (row) =>
          row.edge.id === focus ||
          row.source.key === focus ||
          row.target.key === focus,
      )
    : null
  const isDimmedEdge = (edgeId: string) =>
    focusedRows !== null && !focusedRows.some((row) => row.edge.id === edgeId)
  const isDimmedNode = (key: string) =>
    focusedRows !== null &&
    !focusedRows.some((row) => row.source.key === key || row.target.key === key)
  const isSelectedNode = (key: string) =>
    selected !== undefined &&
    (selected.source.key === key || selected.target.key === key)
  // Đường được chọn vẽ sau cùng để nằm trên các đường khác.
  const ordered = [
    ...rows.filter((row) => row.edge.id !== selectedId),
    ...rows.filter((row) => row.edge.id === selectedId),
  ]

  if (page.edges.length === 0) {
    return <EmptyGraph kind={page.graph_kind} status={page.status} />
  }

  return (
    <div className="flex min-w-0 flex-col gap-space-sm">
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <p className="min-w-0 font-label-sm text-label-sm text-on-surface-variant">
          {page.edges.length < page.total_count
            ? `Sơ đồ đang vẽ ${page.edges.length}/${page.total_count} quan hệ, xem đủ ở kiểu Danh sách. `
            : ''}
          Kéo để di chuyển · Ctrl + cuộn để phóng to · Bấm vào đường nối để xem
          chi tiết
        </p>
        <ZoomControls
          zoom={zoom}
          setZoom={setZoom}
          onReset={() => {
            setZoom(1)
            setOffset({ x: 0, y: 0 })
          }}
        />
      </div>
      <div className="min-w-0 overflow-hidden rounded-lg bg-surface-container-low">
        <div className="max-h-[68vh] min-w-0 overflow-auto">
          <svg
            ref={svgRef}
            aria-label={`Sơ đồ ${page.graph_kind === 'operation' ? 'thay đổi điều khoản' : 'quan hệ giữa điều khoản'}, ${edges.length} quan hệ`}
            className="block h-auto w-full min-w-[720px] touch-none cursor-grab select-none active:cursor-grabbing"
            role="group"
            tabIndex={0}
            viewBox={`0 0 ${WIDTH} ${height}`}
            xmlns="http://www.w3.org/2000/svg"
            onPointerDown={(event) => {
              if ((event.target as Element).closest('[data-graph-hit="true"]'))
                return
              drag.current = {
                pointerId: event.pointerId,
                x: event.clientX,
                y: event.clientY,
              }
              event.currentTarget.setPointerCapture(event.pointerId)
            }}
            onPointerMove={(event) => {
              if (drag.current?.pointerId !== event.pointerId) return
              const bounds = event.currentTarget.getBoundingClientRect()
              const scaleX = WIDTH / Math.max(bounds.width, 1) / zoom
              const scaleY = height / Math.max(bounds.height, 1) / zoom
              const deltaX = (event.clientX - drag.current.x) * scaleX
              const deltaY = (event.clientY - drag.current.y) * scaleY
              drag.current.x = event.clientX
              drag.current.y = event.clientY
              setOffset((current) => ({
                x: current.x + deltaX,
                y: current.y + deltaY,
              }))
            }}
            onPointerUp={(event) => {
              if (drag.current?.pointerId !== event.pointerId) return
              drag.current = null
              event.currentTarget.releasePointerCapture(event.pointerId)
            }}
            onPointerCancel={() => {
              drag.current = null
            }}
            onKeyDown={(event) => {
              if (event.target !== event.currentTarget) return
              if (event.key === '+' || event.key === '=')
                setZoom((value) => clampZoom(value + 0.1))
              if (event.key === '-') setZoom((value) => clampZoom(value - 0.1))
              const step = 40 / zoom
              if (event.key === 'ArrowLeft')
                setOffset((current) => ({ ...current, x: current.x + step }))
              if (event.key === 'ArrowRight')
                setOffset((current) => ({ ...current, x: current.x - step }))
              if (event.key === 'ArrowUp')
                setOffset((current) => ({ ...current, y: current.y + step }))
              if (event.key === 'ArrowDown')
                setOffset((current) => ({ ...current, y: current.y - step }))
            }}
          >
            <defs>
              {RELATION_TONES.map((tone) => (
                <marker
                  key={tone}
                  id={`ai2-graph-arrow-${tone}`}
                  markerHeight="7"
                  markerWidth="7"
                  orient="auto"
                  refX="7"
                  refY="4"
                  viewBox="0 0 8 8"
                >
                  <path
                    d="M0,0 L8,4 L0,8 z"
                    className={relationFillClasses[tone]}
                  />
                </marker>
              ))}
            </defs>
            <g transform={`translate(${offset.x} ${offset.y}) scale(${zoom})`}>
              {ordered.map(({ edge, source, target, path, labelX, labelY }) => {
                const tone = relationTone(edge.label)
                const isSelected = edge.id === selectedId
                const label = relationLabel(edge.label)
                const pillWidth = label.length * 6.8 + 26
                return (
                  <g
                    key={edge.id}
                    aria-label={`${label}: ${source.label} ${edge.directed ? 'đến' : 'và'} ${target.label}${edge.target_address ? `; địa chỉ đích ${edge.target_address}` : ''}`}
                    aria-pressed={isSelected}
                    className="cursor-pointer outline-none transition-opacity focus-visible:outline focus-visible:outline-2"
                    data-graph-hit="true"
                    opacity={isDimmedEdge(edge.id) ? 0.15 : 1}
                    onClick={() => onSelectEdge(edge.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        onSelectEdge(edge.id)
                      }
                    }}
                    onPointerEnter={() => setFocus(edge.id)}
                    onPointerLeave={() => setFocus(null)}
                    onFocus={() => setFocus(edge.id)}
                    onBlur={() => setFocus(null)}
                    role="button"
                    tabIndex={0}
                  >
                    <title>{`${label} · ${edge.review_state === 'NEEDS_REVIEW' ? 'AI đề xuất, cần rà soát' : reviewStateLabel(edge.review_state)}`}</title>
                    {/* Vùng bấm rộng hơn nét vẽ để dễ chọn đường mảnh. */}
                    <path
                      d={path}
                      fill="none"
                      stroke="transparent"
                      strokeWidth={16}
                    />
                    {isSelected ? (
                      <path
                        d={path}
                        fill="none"
                        className={relationStrokeClasses[tone]}
                        strokeOpacity={0.18}
                        strokeWidth={10}
                      />
                    ) : null}
                    <path
                      d={path}
                      fill="none"
                      markerEnd={
                        edge.directed
                          ? `url(#ai2-graph-arrow-${tone})`
                          : undefined
                      }
                      className={relationStrokeClasses[tone]}
                      strokeWidth={isSelected ? 3 : 1.75}
                    />
                    <rect
                      className={
                        isSelected
                          ? relationFillClasses[tone]
                          : `fill-white ${relationStrokeClasses[tone]}`
                      }
                      height="24"
                      rx="12"
                      strokeWidth={1.25}
                      width={pillWidth}
                      x={labelX - pillWidth / 2}
                      y={labelY - 12}
                    />
                    <text
                      className={isSelected ? 'fill-white' : 'fill-on-surface'}
                      fontSize="12"
                      fontWeight={600}
                      textAnchor="middle"
                      x={labelX}
                      y={labelY + 4}
                    >
                      {label}
                    </text>
                  </g>
                )
              })}
              {[...nodes.values()].map((node) => {
                const highlighted = isSelectedNode(node.key)
                const firstEdge = rows.find(
                  (row) =>
                    row.source.key === node.key || row.target.key === node.key,
                )?.edge.id
                const lines = wrapGraphLabel(node.label, 40, node.title ? 2 : 3)
                const textTop = node.title ? node.y + 42 : node.y + 24
                return (
                  <g
                    key={node.key}
                    aria-label={node.label}
                    className="cursor-pointer transition-opacity"
                    data-graph-hit="true"
                    opacity={isDimmedNode(node.key) ? 0.35 : 1}
                    onClick={() => firstEdge && onSelectEdge(firstEdge)}
                    onPointerEnter={() => setFocus(node.key)}
                    onPointerLeave={() => setFocus(null)}
                  >
                    <title>{node.label}</title>
                    <rect
                      className={
                        highlighted
                          ? 'fill-white stroke-brand-500'
                          : 'fill-white stroke-outline-variant'
                      }
                      height={NODE_H}
                      rx="10"
                      strokeWidth={highlighted ? 2 : 1}
                      width={NODE_W}
                      x={node.x}
                      y={node.y}
                    />
                    {node.title ? (
                      <text
                        className="fill-on-surface"
                        fontSize="12"
                        fontWeight={700}
                        x={node.x + 12}
                        y={node.y + 22}
                      >
                        {truncate(node.title, 38)}
                      </text>
                    ) : null}
                    <text
                      className={
                        node.title
                          ? 'fill-on-surface-variant'
                          : 'fill-on-surface'
                      }
                      fontSize="12"
                      x={node.x + 12}
                    >
                      {lines.map((line, index) => (
                        <tspan
                          key={`${index}:${line}`}
                          x={node.x + 12}
                          y={textTop + index * 16}
                        >
                          {line}
                        </tspan>
                      ))}
                    </text>
                  </g>
                )
              })}
            </g>
          </svg>
        </div>
      </div>
    </div>
  )
}

function ZoomControls({
  zoom,
  setZoom,
  onReset,
}: {
  zoom: number
  setZoom: (update: (value: number) => number) => void
  onReset: () => void
}) {
  return (
    <div
      className="inline-flex shrink-0 items-center gap-0.5 rounded-full bg-surface-container p-1"
      aria-label="Điều khiển sơ đồ"
    >
      <button
        className={ZOOM_BUTTON}
        onClick={() => setZoom((value) => clampZoom(value - 0.2))}
        type="button"
        aria-label="Thu nhỏ sơ đồ"
        title="Thu nhỏ"
      >
        <MaterialIcon name="zoom_out" className="text-[18px]" />
      </button>
      <span
        className="min-w-11 text-center font-label-sm text-label-sm tabular-nums text-on-surface-variant"
        aria-live="polite"
      >
        {Math.round(zoom * 100)}%
      </span>
      <button
        className={ZOOM_BUTTON}
        onClick={() => setZoom((value) => clampZoom(value + 0.2))}
        type="button"
        aria-label="Phóng to sơ đồ"
        title="Phóng to"
      >
        <MaterialIcon name="zoom_in" className="text-[18px]" />
      </button>
      <button
        className={ZOOM_BUTTON}
        onClick={onReset}
        type="button"
        aria-label="Đặt lại sơ đồ"
        title="Vừa khung"
      >
        <MaterialIcon name="fit_screen" className="text-[18px]" />
      </button>
    </div>
  )
}

/**
 * Xếp điều khoản thành hai cột: điều khoản nguồn bên trái, đích bên phải. Cột
 * phải sắp theo vị trí trung bình của các nguồn nối tới để đường nối ít cắt
 * nhau; cột ngắn hơn được canh giữa theo cột dài.
 */
function layoutNodes(
  edges: ContractGraphEdge[],
  resolveNodeLabel: NodeLabelResolver,
  resolveNodeTitle?: NodeLabelResolver,
) {
  const nodes = new Map<string, GraphNode>()
  const add = (
    id: string,
    documentId: string | null | undefined,
    column: GraphNode['column'],
    unknownIdentity: string,
    address?: string | null,
  ) => {
    const key = nodeKey(id, documentId, unknownIdentity)
    if (nodes.has(key)) return
    nodes.set(key, {
      key,
      label: [resolveNodeLabel(id, documentId), address]
        .filter(Boolean)
        .join(' · '),
      title: resolveNodeTitle?.(id, documentId) ?? '',
      column,
      x: COLUMN_X[column],
      y: 0,
    })
  }
  for (const edge of edges) {
    add(
      edge.source_node_id,
      edge.source_document_id,
      'left',
      `${edge.id}:source`,
    )
    add(
      edge.target_node_id,
      edge.target_document_id,
      'right',
      `${edge.id}:target`,
      edge.target_address,
    )
  }
  const left = [...nodes.values()].filter((node) => node.column === 'left')
  const leftIndex = new Map(left.map((node, index) => [node.key, index]))
  const neighbours = new Map<string, number[]>()
  for (const edge of edges) {
    const source = nodeKey(
      edge.source_node_id,
      edge.source_document_id,
      `${edge.id}:source`,
    )
    const target = nodeKey(
      edge.target_node_id,
      edge.target_document_id,
      `${edge.id}:target`,
    )
    for (const [a, b] of [
      [source, target],
      [target, source],
    ]) {
      const index = leftIndex.get(b)
      if (index !== undefined && nodes.get(a)?.column === 'right')
        neighbours.set(a, [...(neighbours.get(a) ?? []), index])
    }
  }
  const barycenter = (key: string) => {
    const list = neighbours.get(key)
    return list
      ? list.reduce((sum, value) => sum + value, 0) / list.length
      : Number.POSITIVE_INFINITY
  }
  const right = [...nodes.values()]
    .filter((node) => node.column === 'right')
    .map((node, index) => ({ node, index }))
    .sort(
      (a, b) =>
        barycenter(a.node.key) - barycenter(b.node.key) || a.index - b.index,
    )
    .map(({ node }) => node)
  const tallest = Math.max(left.length, right.length)
  for (const column of [left, right]) {
    const shift = ((tallest - column.length) * ROW) / 2
    column.forEach((node, index) => {
      node.y = PAD + shift + index * ROW
    })
  }
  return nodes
}

/** Đường cong nối hai điều khoản và vị trí nhãn ở giữa đường. */
function edgeGeometry(source: GraphNode, target: GraphNode) {
  const sourceY = source.y + NODE_H / 2
  const targetY = target.y + NODE_H / 2
  if (source.column !== target.column) {
    const leftToRight = source.column === 'left'
    const startX = leftToRight ? source.x + NODE_W : source.x
    const endX = leftToRight ? target.x : target.x + NODE_W
    const middle = (startX + endX) / 2
    return {
      path: `M ${startX} ${sourceY} C ${middle} ${sourceY}, ${middle} ${targetY}, ${endX} ${targetY}`,
      labelX: middle,
      labelY: (sourceY + targetY) / 2,
    }
  }
  // Cùng cột: vòng ra phía giữa sơ đồ rồi quay lại.
  const inward = source.column === 'left' ? 1 : -1
  const edgeX = source.column === 'left' ? source.x + NODE_W : source.x
  const bulge = inward * 140
  return {
    path: `M ${edgeX} ${sourceY} C ${edgeX + bulge} ${sourceY}, ${edgeX + bulge} ${targetY}, ${edgeX} ${targetY}`,
    labelX: edgeX + bulge * 0.75,
    labelY: (sourceY + targetY) / 2,
  }
}

function nodeKey(
  id: string,
  documentId?: string | null,
  unknownIdentity?: string,
) {
  return documentId
    ? `${documentId}:${id}`
    : `unknown:${unknownIdentity ?? id}:${id}`
}

function truncate(value: string, length: number) {
  const compact = value.replace(/\s+/g, ' ').trim()
  return compact.length > length ? `${compact.slice(0, length - 1)}…` : compact
}

function wrapGraphLabel(
  label: string,
  lineLength: number,
  maxLines: number,
): string[] {
  const words = label.replace(/\s+/g, ' ').trim().split(' ')
  const lines: string[] = []
  while (words.length > 0 && lines.length < maxLines) {
    let line = ''
    while (words.length > 0) {
      const next = words[0]
      if (line && line.length + next.length + 1 > lineLength) break
      words.shift()
      line = line ? `${line} ${next}` : next
    }
    lines.push(line || words.shift() || '')
  }
  if (words.length > 0 && lines.length > 0) {
    const last = lines.length - 1
    lines[last] = `${lines[last].slice(0, lineLength - 1)}…`
  }
  return lines
}
