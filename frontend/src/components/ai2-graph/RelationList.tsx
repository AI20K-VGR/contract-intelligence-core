import { useRef, useState } from 'react'
import { relationLabel, reviewStateLabel } from '../../structure/displayLabels'

import type {
  ContractGraphEdge,
  ContractGraphPage,
} from '../../api/contractGraph'
import {
  appendRelationPage,
  createRelationListState,
  graphStatusLabel,
  isRelationListComplete,
} from './contractGraphViewModel'
import { MaterialIcon } from '../icons'
import { RelationInspector } from './RelationInspector'

export function RelationList({
  page,
  onLoadPage,
  onOpenCitation,
  resolveNodeLabel,
  selectedId: controlledSelectedId,
  onSelectEdge,
  onResolveEdgeEvidence,
  citationRecord,
  citationError,
  citationLoading,
}: {
  page: ContractGraphPage
  onLoadPage?: (cursor: string) => Promise<ContractGraphPage>
  onOpenCitation: (
    citationRef: string,
    nodeId: string,
    sourceDocumentId?: string | null,
  ) => void
  resolveNodeLabel?: (nodeId: string, documentId?: string | null) => string
  selectedId?: string | null
  onSelectEdge?: (edgeId: string) => void
  onResolveEdgeEvidence?: (edge: ContractGraphEdge) => Promise<{
    sourceText?: string
    targetText?: string
  } | null>
  citationRecord?: Record<string, unknown> | null
  citationError?: boolean
  citationLoading?: boolean
}) {
  const [state, setState] = useState(() => createRelationListState(page))
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>(
    () => page.edges[0]?.id ?? null,
  )
  const selectedId =
    controlledSelectedId === undefined
      ? internalSelectedId
      : controlledSelectedId
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const inFlight = useRef(false)
  const complete = isRelationListComplete(state)

  async function loadNextPage() {
    if (!onLoadPage || !state.nextCursor || inFlight.current) return
    inFlight.current = true
    setLoading(true)
    setLoadError(false)
    try {
      const cursor = state.nextCursor
      const nextPage = await onLoadPage(cursor)
      setState((current) => appendRelationPage(current, nextPage, cursor))
    } catch {
      setLoadError(true)
    } finally {
      inFlight.current = false
      setLoading(false)
    }
  }

  if (state.status !== 'READY') {
    return (
      <section
        aria-labelledby="ai2-relations-title"
        className="min-w-0 rounded-lg bg-surface-container-lowest p-space-lg shadow-sm"
      >
        <RelationsTitle kind={state.graphKind} />
        <p
          className="mt-space-sm break-words font-body-sm text-body-sm text-on-surface-variant"
          role="status"
        >
          {graphStatusLabel(state.status)}
        </p>
      </section>
    )
  }

  return (
    <section
      aria-labelledby="ai2-relations-title"
      className="min-w-0 rounded-lg bg-surface-container-lowest p-space-lg shadow-sm"
    >
      <RelationsTitle kind={state.graphKind} />
      {state.edges.length === 0 && complete ? (
        <p
          className="mt-space-sm font-body-sm text-body-sm text-on-surface-variant"
          role="status"
        >
          Đã xác nhận: không có quan hệ
        </p>
      ) : (
        <>
          <p
            className="mt-space-xs break-words font-label-sm text-label-sm text-on-surface-variant"
            aria-live="polite"
          >
            Đã tải {state.edges.length}/{state.totalCount} quan hệ
            {complete
              ? ' · Đã tải đầy đủ'
              : state.hasMore
                ? ' · Danh sách chưa tải hết'
                : ' · Tổng số chưa khớp'}
          </p>
          <ul className="mt-space-md flex min-w-0 flex-col gap-space-sm">
            {state.edges.map((edge) => (
              <li key={edge.id} className="min-w-0">
                <RelationRow
                  edge={edge}
                  selected={edge.id === selectedId}
                  onSelect={(id) => {
                    setInternalSelectedId(id)
                    onSelectEdge?.(id)
                    onResolveEdgeEvidence?.(edge)
                  }}
                  resolveNodeLabel={resolveNodeLabel}
                />
                {edge.id === selectedId ? (
                  <div className="mt-space-xs">
                    <RelationInspector
                      edge={edge}
                      onOpenCitation={onOpenCitation}
                      resolveNodeLabel={resolveNodeLabel}
                      citationRecord={citationRecord}
                      citationError={citationError}
                      citationLoading={citationLoading}
                    />
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
          {state.hasMore && state.nextCursor ? (
            <div className="mt-space-md">
              <button
                className="inline-flex items-center gap-space-xs rounded-lg border border-brand-500/70 bg-white px-gutter py-space-sm font-body-sm text-body-sm font-semibold text-on-surface shadow-sm hover:bg-brand-500/5 disabled:opacity-60 focus-visible:outline focus-visible:outline-2"
                disabled={!onLoadPage || loading}
                onClick={loadNextPage}
                type="button"
              >
                {loading ? 'Đang tải quan hệ…' : 'Tải thêm quan hệ'}
              </button>
              {loadError ? (
                <p
                  className="mt-space-sm font-body-sm text-body-sm text-error"
                  role="alert"
                >
                  Không tải được trang tiếp theo. Thử lại để tiếp tục danh sách.
                </p>
              ) : null}
            </div>
          ) : !complete ? (
            <p
              className="mt-space-sm font-body-sm text-body-sm text-error"
              role="status"
            >
              {state.paginationError ??
                'Số quan hệ đã nhận chưa khớp tổng số từ máy chủ.'}
            </p>
          ) : null}
        </>
      )}
    </section>
  )
}

function RelationRow({
  edge,
  selected,
  onSelect,
  resolveNodeLabel = (nodeId) => `Mã điều khoản ${nodeId}`,
}: {
  edge: ContractGraphEdge
  selected: boolean
  onSelect: (id: string) => void
  resolveNodeLabel?: (nodeId: string, documentId?: string | null) => string
}) {
  return (
    <>
      <button
        aria-pressed={selected}
        aria-expanded={selected}
        aria-controls={selected ? 'ai2-selected-relation-detail' : undefined}
        className={`w-full min-w-0 rounded-lg border p-space-md text-left transition-colors focus-visible:outline focus-visible:outline-2 ${
          selected
            ? 'border-brand-300 bg-brand-50'
            : 'border-outline-variant/30 bg-surface-container-lowest hover:bg-surface-container-low'
        }`}
        onClick={() => onSelect(edge.id)}
        type="button"
      >
        <span className="flex flex-wrap items-center gap-space-xs">
          <span className="font-body-sm text-body-sm font-semibold text-on-surface">
            {relationLabel(edge.label)}
          </span>
          <ReviewBadge state={edge.review_state} />
        </span>
        <span className="mt-space-xs grid min-w-0 gap-space-xs font-body-sm text-body-sm text-on-surface-variant sm:grid-cols-[1fr_auto_1fr] sm:items-start">
          <span className="min-w-0 break-words">
            <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wide text-outline">
              Nguồn
            </span>{' '}
            <span
              title={resolveNodeLabel(
                edge.source_node_id,
                edge.source_document_id,
              )}
            >
              {compactRelationText(
                resolveNodeLabel(edge.source_node_id, edge.source_document_id),
              )}
            </span>
          </span>
          <MaterialIcon
            name={edge.directed ? 'arrow_forward' : 'sync_alt'}
            className="hidden text-[18px] text-outline sm:block"
          />
          <span className="min-w-0 break-words">
            <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wide text-outline">
              Đích
            </span>{' '}
            <span
              title={[
                resolveNodeLabel(edge.target_node_id, edge.target_document_id),
                edge.target_address,
              ]
                .filter(Boolean)
                .join(' · ')}
            >
              {compactRelationText(
                [
                  resolveNodeLabel(
                    edge.target_node_id,
                    edge.target_document_id,
                  ),
                  edge.target_address,
                ]
                  .filter(Boolean)
                  .join(' · '),
              )}
            </span>
          </span>
        </span>
      </button>
    </>
  )
}

function RelationsTitle({ kind }: { kind: ContractGraphPage['graph_kind'] }) {
  return (
    <div className="flex items-center gap-space-sm">
      <MaterialIcon
        name="link"
        className="text-[20px] text-on-tertiary-container"
      />
      <h2
        id="ai2-relations-title"
        className="font-title-sm text-title-sm font-semibold text-on-surface"
      >
        {kind === 'operation' ? 'Danh sách sửa đổi' : 'Danh sách quan hệ'}
      </h2>
    </div>
  )
}

/** Nhãn trạng thái rà soát: AI đề xuất thì vàng, đã xác nhận thì xanh. */
export function ReviewBadge({ state }: { state: string }) {
  const needsReview = state === 'NEEDS_REVIEW'
  return (
    <span
      className={`rounded-full px-space-sm py-0.5 font-label-sm text-label-sm font-semibold ${
        needsReview
          ? 'bg-amber-50 text-amber-900'
          : state === 'PASS'
            ? 'bg-emerald-50 text-emerald-800'
            : 'bg-surface-container text-on-surface-variant'
      }`}
    >
      {needsReview ? 'cần rà soát' : reviewStateLabel(state)}
    </span>
  )
}

function compactRelationText(value: string): string {
  const compact = value.replace(/\s+/g, ' ').trim()
  return compact.length > 140 ? `${compact.slice(0, 139)}…` : compact
}
