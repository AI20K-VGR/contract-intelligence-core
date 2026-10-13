import { useCallback, useEffect, useState } from 'react'
import {
  getContractGraphPage,
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
}: {
  enabled: boolean
  dossierId: string
  jobId: string
  snapshotDigest: string
  graphKind: ContractGraphKind
  resolveNodeLabel: (nodeId: string, documentId?: string | null) => string
  onOpenCitation: (citationRef: string, nodeId: string) => void
  onSelectRelation: (edgeId: string) => void
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
            resolveNodeLabel={resolveNodeLabel}
          />
          <RelationList
            key={`${jobId}:${snapshotDigest}:${graphKind}`}
            page={data.page}
            onLoadPage={loadNextPage}
            onOpenCitation={onOpenCitation}
            onSelectEdge={selectRelation}
            resolveNodeLabel={resolveNodeLabel}
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
  const height = Math.max(132, 108 + Math.max(0, nodes.size - 1) * 68)
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
        Sơ đồ chỉ đọc. Không kéo hoặc sửa quan hệ; chọn đường nối để xem chi
        tiết.
      </p>
      {page.edges.length === 0 ? (
        <p className="mt-3" role="status">
          Trang này chưa có quan hệ để vẽ.
        </p>
      ) : (
        <div className="mt-3 max-h-[70vh] min-w-0 overflow-auto rounded border border-outline-variant/50">
          <svg
            aria-label={`Sơ đồ ${page.graph_kind === 'operation' ? 'thay đổi điều khoản' : 'quan hệ giữa điều khoản'}, ${page.edges.length} quan hệ trong trang`}
            className="block h-auto w-full"
            role="group"
            viewBox={`0 0 960 ${height}`}
            xmlns="http://www.w3.org/2000/svg"
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
                  height="44"
                  rx="10"
                  width="260"
                  x={node.x - 130}
                  y={node.y - 22}
                />
                <title>{node.label}</title>
                <text
                  className="fill-on-surface"
                  fontSize="15"
                  textAnchor="middle"
                  x={node.x}
                  y={node.y + 5}
                >
                  {shortLabel(node.label)}
                </text>
              </g>
            ))}
          </svg>
        </div>
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
  if (!nodes.has(key))
    nodes.set(key, {
      label: [resolveNodeLabel(id, documentId), address]
        .filter(Boolean)
        .join(' · '),
      x,
      y: 62 + nodes.size * 68,
    })
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

function shortLabel(label: string): string {
  return label.length > 34 ? `${label.slice(0, 31)}…` : label
}
