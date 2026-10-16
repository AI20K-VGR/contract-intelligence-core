import type { ContractGraphEdge } from '../../api/contractGraph'
import { relationLabel, reviewStateLabel } from '../../structure/displayLabels'
import { MaterialIcon } from '../icons'

const EVIDENCE_BUTTON =
  'inline-flex max-w-full items-center gap-space-xs rounded-lg border border-outline-variant/40 bg-white px-space-md py-space-xs text-left font-body-sm text-body-sm font-semibold text-on-surface shadow-sm hover:bg-surface-container-low focus-visible:outline focus-visible:outline-2'

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
  const citationNodeId =
    typeof citationRecord?.__node_id === 'string'
      ? citationRecord.__node_id
      : null
  const citationDocumentId =
    typeof citationRecord?.__document_id === 'string'
      ? citationRecord.__document_id
      : null
  const citationSide =
    citationNodeId === edge.source_node_id &&
    citationDocumentId === edge.source_document_id
      ? 'nguồn'
      : citationNodeId === edge.target_node_id &&
          citationDocumentId === edge.target_document_id
        ? 'đích'
        : null
  return (
    <aside
      id="ai2-selected-relation-detail"
      aria-label="Chi tiết quan hệ được chọn"
      className="min-w-0 rounded-lg bg-surface-container-low p-space-md"
    >
      <h3 className="font-label-md text-label-md font-semibold text-on-surface">
        Chi tiết quan hệ
      </h3>
      <dl className="mt-space-sm grid min-w-0 gap-space-sm font-body-sm text-body-sm">
        <div className="flex min-w-0 flex-wrap gap-x-space-lg gap-y-space-xs">
          <div className="min-w-0">
            <dt className="font-label-sm text-label-sm text-on-surface-variant">
              Loại quan hệ
            </dt>
            <dd className="break-words font-semibold text-on-surface">
              {relationLabel(edge.label)}
            </dd>
          </div>
          <div>
            <dt className="font-label-sm text-label-sm text-on-surface-variant">
              Trạng thái rà soát
            </dt>
            <dd className="font-semibold text-on-surface">
              {edge.review_state === 'NEEDS_REVIEW'
                ? 'AI đề xuất · cần rà soát'
                : reviewStateLabel(edge.review_state)}
            </dd>
          </div>
        </div>
        <div className="min-w-0">
          <dt className="font-label-sm text-label-sm text-on-surface-variant">
            Điều khoản nguồn
          </dt>
          <dd className="mt-0.5 max-h-28 overflow-auto whitespace-pre-wrap break-words rounded-md bg-white p-space-sm text-on-surface">
            {resolveNodeLabel(edge.source_node_id, edge.source_document_id)}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="font-label-sm text-label-sm text-on-surface-variant">
            Điều khoản đích
          </dt>
          <dd className="mt-0.5 max-h-28 overflow-auto whitespace-pre-wrap break-words rounded-md bg-white p-space-sm text-on-surface">
            {[
              resolveNodeLabel(edge.target_node_id, edge.target_document_id),
              edge.target_address,
            ]
              .filter(Boolean)
              .join(' · ')}
          </dd>
        </div>
      </dl>
      <div className="mt-space-md flex min-w-0 flex-wrap gap-space-sm">
        <button
          className={EVIDENCE_BUTTON}
          onClick={() =>
            onOpenCitation(
              edge.source_citation_ref,
              edge.source_node_id,
              edge.source_document_id,
            )
          }
          type="button"
        >
          <MaterialIcon name="format_quote" className="text-[16px]" />
          Mở bằng chứng nguồn
        </button>
        <button
          className={EVIDENCE_BUTTON}
          onClick={() =>
            onOpenCitation(
              edge.target_citation_ref,
              edge.target_node_id,
              edge.target_document_id,
            )
          }
          type="button"
        >
          <MaterialIcon name="format_quote" className="text-[16px]" />
          Mở bằng chứng đích
        </button>
      </div>
      {citationLoading ? (
        <p
          className="mt-space-md flex items-center gap-space-sm font-body-sm text-body-sm text-on-surface-variant"
          role="status"
        >
          <MaterialIcon
            name="progress_activity"
            className="animate-spin text-[16px] text-primary"
          />
          Đang tải bằng chứng…
        </p>
      ) : typeof citationRecord?.quote === 'string' ? (
        <section
          className="mt-space-md rounded-md border-l-4 border-brand-500 bg-white p-space-md"
          aria-label={`Bằng chứng ${citationSide ?? 'quan hệ'}`}
        >
          <h4 className="font-label-md text-label-md font-semibold text-on-surface">
            Bằng chứng {citationSide ?? 'quan hệ'}
          </h4>
          <p className="mt-space-xs max-h-40 overflow-auto whitespace-pre-wrap break-words font-body-sm text-body-sm text-on-surface">
            {citationRecord.quote}
          </p>
          {typeof citationRecord.page === 'number' ? (
            <p className="mt-space-xs font-label-sm text-label-sm text-on-surface-variant">
              Trang {citationRecord.page}
            </p>
          ) : null}
        </section>
      ) : citationError ? (
        <p
          className="mt-space-md font-body-sm text-body-sm text-error"
          role="alert"
        >
          Không tải được bằng chứng cho quan hệ này.
        </p>
      ) : null}
    </aside>
  )
}
