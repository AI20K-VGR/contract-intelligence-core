import type { ReactNode } from 'react'

import type { ContractGraphEdge } from '../../api/contractGraph'
import { MaterialIcon } from '../icons'
import { RelationBadge, ReviewBadge } from './RelationBadges'

const EVIDENCE_BUTTON =
  'inline-flex shrink-0 items-center gap-space-xs rounded-full px-space-sm py-0.5 font-label-sm text-label-sm font-semibold text-primary hover:bg-brand-50 focus-visible:outline focus-visible:outline-2'

export function RelationInspector({
  edge,
  onOpenCitation,
  resolveNodeLabel = (nodeId) => `Mã điều khoản ${nodeId}`,
  resolveNodeTitle,
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
  resolveNodeTitle?: (nodeId: string, documentId?: string | null) => string
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
  const evidence = (
    <>
      {citationLoading ? (
        <p
          className="flex items-center gap-space-sm font-body-sm text-body-sm text-on-surface-variant"
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
          className="rounded-md border-l-4 border-brand-500 bg-white p-space-sm"
          aria-label={`Bằng chứng ${citationSide ?? 'quan hệ'}`}
        >
          <h4 className="font-label-sm text-label-sm font-semibold text-on-surface-variant">
            Bằng chứng {citationSide ?? 'quan hệ'}
            {typeof citationRecord.page === 'number'
              ? ` · Trang ${citationRecord.page}`
              : ''}
          </h4>
          <p className="mt-space-xs max-h-40 overflow-auto whitespace-pre-wrap break-words font-body-sm text-body-sm text-on-surface">
            {citationRecord.quote}
          </p>
        </section>
      ) : citationError ? (
        <p className="font-body-sm text-body-sm text-error" role="alert">
          Không tải được bằng chứng cho quan hệ này.
        </p>
      ) : null}
    </>
  )
  return (
    <aside
      id="ai2-selected-relation-detail"
      aria-label="Chi tiết quan hệ được chọn"
      className="flex min-w-0 flex-col gap-space-sm rounded-lg bg-surface-container-low p-space-md"
    >
      <div className="flex flex-wrap items-center gap-space-xs">
        <RelationBadge label={edge.label} />
        <ReviewBadge state={edge.review_state} />
      </div>
      <ClauseCard
        heading="Điều khoản nguồn"
        title={resolveNodeTitle?.(edge.source_node_id, edge.source_document_id)}
        text={resolveNodeLabel(edge.source_node_id, edge.source_document_id)}
        action={
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
            title="Mở bằng chứng nguồn"
          >
            <MaterialIcon name="format_quote" className="text-[16px]" />
            Mở bằng chứng nguồn
          </button>
        }
      />
      {citationSide === 'nguồn' ? evidence : null}
      <MaterialIcon
        name={edge.directed ? 'arrow_downward' : 'sync_alt'}
        className={`self-center text-[20px] text-outline ${edge.directed ? '' : 'rotate-90'}`}
      />
      <ClauseCard
        heading="Điều khoản đích"
        title={resolveNodeTitle?.(edge.target_node_id, edge.target_document_id)}
        text={[
          resolveNodeLabel(edge.target_node_id, edge.target_document_id),
          edge.target_address,
        ]
          .filter(Boolean)
          .join(' · ')}
        action={
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
            title="Mở bằng chứng đích"
          >
            <MaterialIcon name="format_quote" className="text-[16px]" />
            Mở bằng chứng đích
          </button>
        }
      />
      {citationSide === 'nguồn' ? null : evidence}
    </aside>
  )
}

function ClauseCard({
  heading,
  title,
  text,
  action,
}: {
  heading: string
  title?: string
  text: string
  action: ReactNode
}) {
  return (
    <div className="min-w-0 rounded-md bg-white p-space-sm shadow-[0_1px_2px_rgba(15,23,42,0.06)]">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-space-sm">
        <span className="min-w-0 font-label-sm text-label-sm font-semibold uppercase tracking-wide text-outline">
          {heading}
        </span>
        {action}
      </div>
      {title ? (
        <p className="mt-space-xs break-words font-body-sm text-body-sm font-semibold text-on-surface">
          {title}
        </p>
      ) : null}
      <p className="mt-space-xs max-h-40 overflow-auto whitespace-pre-wrap break-words font-body-sm text-body-sm text-on-surface">
        {text}
      </p>
    </div>
  )
}
