import type { ContractGraphEdge } from '../../api/contractGraph'
import { MaterialIcon } from '../icons'
import { RelationBadge, ReviewBadge } from './RelationBadges'

export function RelationInspector({
  edge,
  onBack,
  showLabel = true,
  onOpenEvidence,
  evidenceOpen = false,
  resolveNodeLabel = (nodeId) => `Mã điều khoản ${nodeId}`,
  resolveNodeTitle,
}: {
  edge: ContractGraphEdge
  /** Về khung tổng hợp tất cả quan hệ (bỏ chọn quan hệ này). */
  onBack?: () => void
  /** Hiện nhãn loại quan hệ (ẩn khi hồ sơ chỉ có một loại). */
  showLabel?: boolean
  /** Mở hai tài liệu của quan hệ như màn đối soát (nguồn và đích). */
  onOpenEvidence: (edge: ContractGraphEdge) => void
  /** Khung bằng chứng của quan hệ này đang mở. */
  evidenceOpen?: boolean
  resolveNodeLabel?: (nodeId: string, documentId?: string | null) => string
  resolveNodeTitle?: (nodeId: string, documentId?: string | null) => string
}) {
  return (
    <aside
      id="ai2-selected-relation-detail"
      aria-label="Chi tiết quan hệ được chọn"
      className="flex min-w-0 flex-col gap-space-sm rounded-lg bg-surface-container-low p-space-md"
    >
      <div className="flex items-center justify-between gap-space-xs">
        {onBack ? (
          <button
            className="inline-flex items-center gap-space-xs rounded-full py-0.5 pr-space-sm font-label-sm text-label-sm font-semibold text-primary hover:bg-brand-50 focus-visible:outline focus-visible:outline-2"
            type="button"
            onClick={onBack}
          >
            <MaterialIcon name="arrow_back" className="text-[16px]" />
            Tất cả quan hệ
          </button>
        ) : (
          <span />
        )}
        {/* Nút nhỏ chỉ có viền, sát mép phải, cùng hàng với "Tất cả quan hệ". */}
        <button
          aria-pressed={evidenceOpen}
          className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 font-label-sm text-[12px] font-semibold focus-visible:outline focus-visible:outline-2 ${
            evidenceOpen
              ? 'border-brand-500 text-brand-700 hover:bg-brand-50'
              : 'border-primary/60 text-primary hover:bg-brand-50'
          }`}
          onClick={() => onOpenEvidence(edge)}
          type="button"
        >
          <MaterialIcon
            name={evidenceOpen ? 'close' : 'compare'}
            className="text-[14px]"
          />
          {evidenceOpen ? 'Đóng bằng chứng' : 'Mở bằng chứng'}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-space-xs">
        {showLabel ? <RelationBadge label={edge.label} /> : null}
        <ReviewBadge state={edge.review_state} />
      </div>
      <ClauseCard
        heading="Điều khoản nguồn"
        mark="amber"
        title={resolveNodeTitle?.(edge.source_node_id, edge.source_document_id)}
        text={resolveNodeLabel(edge.source_node_id, edge.source_document_id)}
      />
      <MaterialIcon
        name={edge.directed ? 'arrow_downward' : 'sync_alt'}
        className={`self-center text-[20px] text-outline ${edge.directed ? '' : 'rotate-90'}`}
      />
      <ClauseCard
        heading="Điều khoản đích"
        mark="sky"
        title={resolveNodeTitle?.(edge.target_node_id, edge.target_document_id)}
        text={[
          resolveNodeLabel(edge.target_node_id, edge.target_document_id),
          edge.target_address,
        ]
          .filter(Boolean)
          .join(' · ')}
      />
    </aside>
  )
}

function ClauseCard({
  heading,
  mark,
  title,
  text,
}: {
  heading: string
  /** Cùng màu khung khoanh trên tài liệu khi mở bằng chứng. */
  mark: 'amber' | 'sky'
  title?: string
  text: string
}) {
  return (
    <div className="min-w-0 rounded-md bg-white p-space-sm shadow-[0_1px_2px_rgba(15,23,42,0.06)]">
      <span className="inline-flex min-w-0 items-center gap-1.5 font-label-sm text-label-sm font-semibold uppercase tracking-wide text-outline">
        <span
          aria-hidden
          className={`h-2.5 w-2.5 shrink-0 rounded-sm ${mark === 'sky' ? 'bg-sky-500' : 'bg-amber-500'}`}
        />
        {heading}
      </span>
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
