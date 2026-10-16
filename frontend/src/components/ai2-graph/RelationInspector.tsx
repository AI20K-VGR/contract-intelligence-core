import type { ContractGraphEdge } from '../../api/contractGraph'
import { relationLabel, reviewStateLabel } from '../../structure/displayLabels'

export function RelationInspector({
  edge,
  onOpenCitation,
  resolveNodeLabel = (nodeId) => `Mã điều khoản ${nodeId}`,
  citationRecord,
  citationError = false,
  citationLoading = false,
}: {
  edge: ContractGraphEdge
  onOpenCitation: (
    citationRef: string,
    nodeId: string,
    sourceDocumentId?: string | null,
  ) => void
  resolveNodeLabel?: (nodeId: string, documentId?: string | null) => string
  citationRecord?: Record<string, unknown> | null
  citationError?: boolean
  citationLoading?: boolean
}) {
  const citationNodeId = typeof citationRecord?.__node_id === 'string'
    ? citationRecord.__node_id
    : null
  const citationDocumentId = typeof citationRecord?.__document_id === 'string'
    ? citationRecord.__document_id
    : null
  const citationSide = citationNodeId === edge.source_node_id && citationDocumentId === edge.source_document_id
    ? 'nguồn'
    : citationNodeId === edge.target_node_id && citationDocumentId === edge.target_document_id
      ? 'đích'
      : null
  return (
    <aside
      id="ai2-selected-relation-detail"
      aria-label="Chi tiết quan hệ được chọn"
      className="min-w-0 rounded-lg border border-outline-variant p-3"
    >
      <h3 className="font-title-sm font-semibold">Chi tiết quan hệ</h3>
      <dl className="mt-2 grid min-w-0 gap-2 text-sm">
        <div className="min-w-0">
          <dt className="font-semibold">Loại quan hệ</dt>
          <dd className="break-words">{relationLabel(edge.label)}</dd>
        </div>
        <div className="min-w-0">
          <dt className="font-semibold">Điều khoản nguồn</dt>
          <dd className="max-h-28 overflow-auto whitespace-pre-wrap break-words rounded bg-surface-container-low p-2 text-sm">
            {resolveNodeLabel(edge.source_node_id, edge.source_document_id)}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="font-semibold">Điều khoản đích</dt>
          <dd className="max-h-28 overflow-auto whitespace-pre-wrap break-words rounded bg-surface-container-low p-2 text-sm">
            {[
              resolveNodeLabel(edge.target_node_id, edge.target_document_id),
              edge.target_address,
            ]
              .filter(Boolean)
              .join(' · ')}
          </dd>
        </div>
        <div>
          <dt className="font-semibold">Trạng thái rà soát</dt>
          <dd>
            {edge.review_state === 'NEEDS_REVIEW'
              ? 'AI đề xuất · cần rà soát'
              : reviewStateLabel(edge.review_state)}
          </dd>
        </div>
      </dl>
      <div className="mt-3 flex min-w-0 flex-wrap gap-2">
        <button
          className="min-h-11 max-w-full rounded border border-outline px-3 py-2 text-left focus-visible:outline focus-visible:outline-2"
          onClick={() =>
            onOpenCitation(
              edge.source_citation_ref,
              edge.source_node_id,
              edge.source_document_id,
            )
          }
          type="button"
        >
          Mở bằng chứng nguồn
        </button>
        <button
          className="min-h-11 max-w-full rounded border border-outline px-3 py-2 text-left focus-visible:outline focus-visible:outline-2"
          onClick={() =>
            onOpenCitation(
              edge.target_citation_ref,
              edge.target_node_id,
              edge.target_document_id,
            )
          }
          type="button"
        >
          Mở bằng chứng đích
        </button>
      </div>
      {citationLoading ? (
        <p className="mt-3" role="status">Đang tải bằng chứng…</p>
      ) : typeof citationRecord?.quote === 'string' ? (
        <section className="mt-3 rounded-md border border-outline-variant p-3" aria-label={`Bằng chứng ${citationSide ?? 'quan hệ'}`}>
          <h4 className="font-semibold">Bằng chứng {citationSide ?? 'quan hệ'}</h4>
          <p className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-words">{citationRecord.quote}</p>
          {typeof citationRecord.page === 'number' ? <p className="mt-2 text-xs text-on-surface-variant">Trang {citationRecord.page}</p> : null}
        </section>
      ) : citationError ? (
        <p className="mt-3 text-error" role="alert">Không tải được bằng chứng cho quan hệ này.</p>
      ) : null}
    </aside>
  )
}
