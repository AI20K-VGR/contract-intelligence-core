import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getContractGraphPage,
  type ContractGraphEdge,
  type ContractGraphKind,
  type ContractGraphPage,
  type ProcessingTrace,
} from '../../api/contractGraph'
import { loadAi2GraphDataIfVisible } from './contractGraphRuntime'
import { ProcessingTimeline } from './ProcessingTimeline'
import { RelationList } from './RelationList'

export function Ai2GraphDossierView({
  enabled,
  dossierId,
  jobId,
  snapshotDigest,
  graphKind,
  resolveNodeLabel,
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
  resolveNodeLabel: (nodeId: string, documentId?: string | null) => string
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
  const [resolvedEvidence, setResolvedEvidence] = useState<Record<string, string>>({})
  const resolveEdgeEvidenceRef = useRef(onResolveEdgeEvidence)
  const evidenceRequests = useRef(new Map<string, Promise<{
    sourceText?: string
    targetText?: string
  } | null>>())
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

  const resolveAndStoreEdgeEvidence = useCallback(
    (edge: ContractGraphEdge) => {
      const pending = evidenceRequests.current.get(edge.id)
      if (pending) return pending
      const resolver = resolveEdgeEvidenceRef.current
      if (!resolver) return Promise.resolve(null)
      const request = resolver(edge).then((evidence) => {
      if (evidence) {
        setResolvedEvidence((current) => ({
          ...current,
          ...(evidence.sourceText && edge.source_document_id
            ? { [`${edge.source_document_id}\u0000${edge.source_node_id}`]: evidence.sourceText }
            : {}),
          ...(evidence.targetText && edge.target_document_id
            ? { [`${edge.target_document_id}\u0000${edge.target_node_id}`]: evidence.targetText }
            : {}),
        }))
      }
      return evidence
      }).finally(() => {
        evidenceRequests.current.delete(edge.id)
      })
      evidenceRequests.current.set(edge.id, request)
      return request
    },
    [],
  )

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
      (documentId ? resolvedEvidence[`${documentId}\u0000${nodeId}`] : undefined) ||
      resolveNodeLabel(nodeId, documentId),
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

  if (loading) return <p role="status">Đang tải graph và dấu vết xử lý AI2…</p>
  if (error || !data)
    return (
      <div
        role="alert"
        className="flex min-w-0 flex-col items-start gap-2 rounded border border-error p-3"
      >
        <p>
          Không tải được graph AI2. Kiểm tra quyền đọc trích dẫn hoặc thử lại
          sau.
        </p>
        <button
          className="min-h-11 rounded border border-outline px-3 py-2 focus-visible:outline focus-visible:outline-2"
          onClick={() => setRetry((value) => value + 1)}
          type="button"
        >
          Thử tải lại
        </button>
      </div>
    )
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <ProcessingTimeline trace={data.trace} />
      {data.graphError || !data.page ? (
        <div
          role="alert"
          className="flex min-w-0 flex-col items-start gap-2 rounded border border-error p-3"
        >
          <p>
            Không tải được graph AI2. Dấu vết xử lý vẫn được hiển thị riêng.
          </p>
          <button
            className="min-h-11 rounded border border-outline px-3 py-2 focus-visible:outline focus-visible:outline-2"
            onClick={() => setRetry((value) => value + 1)}
            type="button"
          >
            Thử tải graph lại
          </button>
        </div>
      ) : (
        <>
          <ContractGraphCanvas
            page={data.page}
            selectedId={selectedId}
            onSelectEdge={selectRelation}
            resolveNodeLabel={resolveVisibleNodeLabel}
          />
          <RelationList
            key={`${jobId}:${snapshotDigest}:${graphKind}`}
            page={data.page}
            onLoadPage={loadNextPage}
            onOpenCitation={onOpenCitation}
            onResolveEdgeEvidence={resolveAndStoreEdgeEvidence}
            onSelectEdge={selectRelation}
            resolveNodeLabel={resolveVisibleNodeLabel}
            citationRecord={citationRecord}
            citationError={citationError}
            citationLoading={citationLoading}
            selectedId={selectedId}
          />
        </>
      )}
    </div>
  )
}

export function ContractGraphCanvas({
  page,
  selectedId,
  onSelectEdge,
  resolveNodeLabel = (nodeId) => `Mã điều khoản ${nodeId}`,
}: {
  page: ContractGraphPage
  selectedId: string | null
  onSelectEdge: (edgeId: string) => void
  resolveNodeLabel?: (nodeId: string, documentId?: string | null) => string
}) {
  const nodes = new Map<string, { label: string; x: number; y: number }>()
  for (const edge of page.edges) {
    addNode(
      nodes,
      edge.source_node_id,
      edge.source_document_id,
      190,
      resolveNodeLabel,
      null,
      `${edge.id}:source`,
    )
    addNode(
      nodes,
      edge.target_node_id,
      edge.target_document_id,
      770,
      resolveNodeLabel,
      edge.target_address,
      `${edge.id}:target`,
    )
  }
  const height = Math.max(196, 160 + Math.max(0, nodes.size - 1) * 144)
  const width = 960
  const [zoom, setZoom] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const drag = useRef<{ pointerId: number; x: number; y: number } | null>(null)
  const positions = new Map([...nodes].map(([id, node]) => [id, node]))
  const rows = page.edges.map((edge) => ({
    edge,
    source: positions.get(
      nodeKey(
        edge.source_node_id,
        edge.source_document_id,
        `${edge.id}:source`,
      ),
    )!,
    target: positions.get(
      nodeKey(
        edge.target_node_id,
        edge.target_document_id,
        `${edge.id}:target`,
      ),
    )!,
  }))

  return (
    <section
      aria-labelledby="ai2-graph-canvas-title"
      className="min-w-0 rounded-lg border border-outline-variant p-3"
    >
      <h2 id="ai2-graph-canvas-title" className="font-title-md font-semibold">
        Sơ đồ quan hệ AI2
      </h2>
      <p className="mt-1 break-words text-sm" role="status">
        Đang xem {page.edges.length}/{page.total_count} quan hệ trong trang này;
        danh sách bên dưới tải theo trang.
      </p>
      <p className="mt-1 text-sm text-on-surface-variant">
        Kéo vùng trống để di chuyển; dùng con lăn chuột hoặc nút +/- để phóng to. Chọn đường nối để xem chi tiết.
      </p>
      {page.edges.length === 0 ? (
        <p className="mt-3" role="status">
          Trang này chưa có quan hệ để vẽ.
        </p>
      ) : (
        <>
          <div className="mt-3 flex flex-wrap items-center justify-end gap-2" aria-label="Điều khiển sơ đồ">
            <button className="min-h-11 min-w-11 rounded border border-outline px-3 focus-visible:outline focus-visible:outline-2" onClick={() => setZoom((value) => Math.max(0.6, Math.round((value - 0.2) * 10) / 10))} type="button" aria-label="Thu nhỏ sơ đồ">−</button>
            <span className="min-w-14 text-center text-sm" aria-live="polite">{Math.round(zoom * 100)}%</span>
            <button className="min-h-11 min-w-11 rounded border border-outline px-3 focus-visible:outline focus-visible:outline-2" onClick={() => setZoom((value) => Math.min(2.5, Math.round((value + 0.2) * 10) / 10))} type="button" aria-label="Phóng to sơ đồ">+</button>
            <button className="min-h-11 rounded border border-outline px-3 focus-visible:outline focus-visible:outline-2" onClick={() => { setZoom(1); setOffset({ x: 0, y: 0 }) }} type="button">Đặt lại</button>
          </div>
          <div className="mt-2 max-h-[70vh] min-w-0 overflow-auto rounded border border-outline-variant/50">
          <svg
            aria-label={`Sơ đồ ${page.graph_kind === 'operation' ? 'thay đổi điều khoản' : 'quan hệ giữa điều khoản'}, ${page.edges.length} quan hệ trong trang`}
            className="block h-auto min-w-[900px] w-full touch-none cursor-grab active:cursor-grabbing"
            role="group"
            tabIndex={0}
            viewBox={`0 0 ${width} ${height}`}
            xmlns="http://www.w3.org/2000/svg"
            onPointerDown={(event) => {
              if ((event.target as Element).closest('[data-graph-edge="true"]')) return
              drag.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY }
              event.currentTarget.setPointerCapture(event.pointerId)
            }}
            onPointerMove={(event) => {
              if (drag.current?.pointerId !== event.pointerId) return
              const bounds = event.currentTarget.getBoundingClientRect()
              const scaleX = width / Math.max(bounds.width, 1) / zoom
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
            onPointerCancel={() => { drag.current = null }}
            onWheel={(event) => {
              event.preventDefault()
              setZoom((value) => Math.max(0.6, Math.min(2.5, Math.round((value + (event.deltaY < 0 ? 0.1 : -0.1)) * 10) / 10)))
            }}
            onKeyDown={(event) => {
              if (event.key === '+' || event.key === '=') setZoom((value) => Math.min(2.5, value + 0.1))
              if (event.key === '-') setZoom((value) => Math.max(0.6, value - 0.1))
              const step = 40 / zoom
              if (event.key === 'ArrowLeft') setOffset((current) => ({ ...current, x: current.x + step }))
              if (event.key === 'ArrowRight') setOffset((current) => ({ ...current, x: current.x - step }))
              if (event.key === 'ArrowUp') setOffset((current) => ({ ...current, y: current.y + step }))
              if (event.key === 'ArrowDown') setOffset((current) => ({ ...current, y: current.y - step }))
            }}
          >
            <defs>
              <marker
                id="ai2-graph-arrow"
                markerHeight="8"
                markerWidth="8"
                orient="auto"
                refX="7"
                refY="4"
                viewBox="0 0 8 8"
              >
                <path d="M0,0 L8,4 L0,8 z" fill="currentColor" />
              </marker>
            </defs>
            <g transform={`translate(${offset.x} ${offset.y}) scale(${zoom})`}>
            {rows.map(({ edge, source, target }) => (
              <g
                key={edge.id}
                aria-label={`${edge.label}: ${source.label} ${edge.directed ? 'đến' : 'và'} ${target.label}${edge.target_address ? `; địa chỉ đích ${edge.target_address}` : ''}`}
                aria-pressed={selectedId === edge.id}
                className="cursor-pointer focus:outline focus:outline-2"
                onClick={() => onSelectEdge(edge.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onSelectEdge(edge.id)
                  }
                }}
                role="button"
                tabIndex={0}
                data-graph-edge="true"
              >
                <title>{`${edge.label} · ${edge.review_state === 'NEEDS_REVIEW' ? 'AI2 đề xuất, cần review' : edge.review_state}`}</title>
                <path
                  d={`M ${source.x + 132} ${source.y} C 400 ${source.y}, 560 ${target.y}, ${target.x - 132} ${target.y}`}
                  fill="none"
                  markerEnd={
                    edge.directed ? 'url(#ai2-graph-arrow)' : undefined
                  }
                  stroke={selectedId === edge.id ? 'currentColor' : '#64748b'}
                  strokeWidth={selectedId === edge.id ? 4 : 2}
                />
                <rect
                  className="fill-surface stroke-outline"
                  height="30"
                  rx="8"
                  width="260"
                  x="350"
                  y={(source.y + target.y) / 2 - 15}
                />
                <text
                  className="fill-on-surface"
                  fontSize="13"
                  textAnchor="middle"
                  x="480"
                  y={(source.y + target.y) / 2 + 5}
                >
                  {edge.label} ·{' '}
                  {edge.review_state === 'NEEDS_REVIEW'
                    ? 'cần review'
                    : edge.review_state}
                </text>
              </g>
            ))}
            {[...nodes].map(([id, node]) => (
              <g key={id} aria-label={node.label}>
                <rect
                  className="fill-surface-container-low stroke-outline"
                  height="124"
                  rx="10"
                  width="280"
                  x={node.x - 140}
                  y={node.y - 62}
                />
                <title>{node.label}</title>
                <text
                  className="fill-on-surface"
                  fontSize="12"
                  textAnchor="middle"
                  x={node.x}
                >
                  {wrapGraphLabel(node.label, 39, 6).map((line, index) => (
                    <tspan key={`${index}:${line}`} x={node.x} y={node.y - 40 + index * 17}>
                      {line}
                    </tspan>
                  ))}
                </text>
              </g>
            ))}
            </g>
          </svg>
          </div>
        </>
      )}
    </section>
  )
}

function addNode(
  nodes: Map<string, { label: string; x: number; y: number }>,
  id: string,
  documentId: string | null | undefined,
  x: number,
  resolveNodeLabel: (nodeId: string, documentId?: string | null) => string,
  address?: string | null,
  unknownIdentity?: string,
) {
  const key = nodeKey(id, documentId, unknownIdentity)
  if (!nodes.has(key)) {
    const label = [resolveNodeLabel(id, documentId), address]
      .filter(Boolean)
      .join(' · ')
    nodes.set(key, {
      label,
      x,
      y: 96 + nodes.size * 144,
    })
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

function wrapGraphLabel(label: string, lineLength: number, maxLines: number): string[] {
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
