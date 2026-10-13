import type { ContractGraphEdge } from '../../api/contractGraph'

export function RelationInspector({
  edge,
  onOpenCitation,
  resolveNodeLabel = (nodeId) => `Mã điều khoản ${nodeId}`,
}: {
  edge: ContractGraphEdge
  onOpenCitation: (
    citationRef: string,
    nodeId: string,
    sourceDocumentId?: string | null,
  ) => void
  resolveNodeLabel?: (nodeId: string, documentId?: string | null) => string
}) {
  return (
    <aside
      aria-label="Chi tiết quan hệ được chọn"
      className="min-w-0 rounded-lg border border-outline-variant p-3"
    >
      <h3 className="font-title-sm font-semibold">Chi tiết quan hệ</h3>
      <dl className="mt-2 grid min-w-0 gap-2 text-sm">
        <div className="min-w-0">
          <dt className="font-semibold">Loại quan hệ</dt>
          <dd className="break-words">{edge.label}</dd>
        </div>
        <div className="min-w-0">
          <dt className="font-semibold">Điều khoản nguồn</dt>
          <dd className="break-words">
            {resolveNodeLabel(edge.source_node_id, edge.source_document_id)}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="font-semibold">Điều khoản đích</dt>
          <dd className="break-words">
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
              ? 'AI2 đề xuất · cần review'
              : edge.review_state}
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
    </aside>
  )
}
