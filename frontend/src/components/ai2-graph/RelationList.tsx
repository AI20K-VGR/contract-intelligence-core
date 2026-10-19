import { useEffect, useRef, useState } from 'react'
import { relationLabel } from '../../structure/displayLabels'

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
import { RelationBadge, ReviewBadge } from './RelationBadges'
import { RelationInspector } from './RelationInspector'
import { hasSeveralRelationTypes } from './relationTone'

type NodeLabelResolver = (nodeId: string, documentId?: string | null) => string

export function RelationList({
  page,
  filter = null,
  onLoadPage,
  onOpenEvidence,
  evidenceEdgeId = null,
  resolveNodeLabel,
  resolveNodeTitle,
  selectedId: controlledSelectedId,
  onSelectEdge,
  onResolveEdgeEvidence,
  onEdgesChange,
}: {
  page: ContractGraphPage
  /** Chỉ hiện loại quan hệ này (tên hiển thị); null là hiện tất cả. */
  filter?: string | null
  onLoadPage?: (cursor: string) => Promise<ContractGraphPage>
  onOpenEvidence: (edge: ContractGraphEdge) => void
  /** Quan hệ đang mở khung bằng chứng. */
  evidenceEdgeId?: string | null
  resolveNodeLabel?: NodeLabelResolver
  resolveNodeTitle?: NodeLabelResolver
  selectedId?: string | null
  onSelectEdge?: (edgeId: string) => void
  onResolveEdgeEvidence?: (edge: ContractGraphEdge) => Promise<{
    sourceText?: string
    targetText?: string
  } | null>
  /**
   * Báo mọi cạnh đã tải (cả các trang tải thêm) và đã tải hết chưa, để chú
   * thích và bộ lọc ở component cha biết cả các loại quan hệ của trang sau.
   */
  onEdgesChange?: (edges: ContractGraphEdge[], complete: boolean) => void
}) {
  const [state, setState] = useState(() => createRelationListState(page))
  const reportEdges = useRef(onEdgesChange)
  useEffect(() => {
    reportEdges.current = onEdgesChange
  })
  useEffect(() => {
    reportEdges.current?.(state.edges, isRelationListComplete(state))
  }, [state])
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
      <p
        className="break-words rounded-lg bg-surface-container-low px-space-md py-space-sm font-body-sm text-body-sm text-on-surface-variant"
        role="status"
      >
        {graphStatusLabel(state.status)}
      </p>
    )
  }

  if (state.edges.length === 0 && complete) {
    return (
      <p
        className="rounded-lg bg-surface-container-low px-space-md py-space-sm font-body-sm text-body-sm text-on-surface-variant"
        role="status"
      >
        Đã xác nhận: không có quan hệ
      </p>
    )
  }

  const edges = filter
    ? state.edges.filter((edge) => relationLabel(edge.label) === filter)
    : state.edges
  const selectedEdge = edges.find((edge) => edge.id === selectedId) ?? null
  const showLabel = hasSeveralRelationTypes(state.edges, state.hasMore)

  return (
    <div className="grid min-w-0 items-start gap-gutter lg:grid-cols-[minmax(0,1fr)_340px] 2xl:grid-cols-[minmax(0,1fr)_400px]">
      <section aria-label="Danh sách quan hệ" className="flex min-w-0 flex-col">
        <ul className="flex min-w-0 flex-col gap-space-xs">
          {edges.map((edge) => (
            <li key={edge.id} className="min-w-0">
              <RelationRow
                edge={edge}
                selected={edge.id === selectedId}
                showLabel={showLabel}
                onSelect={(id) => {
                  setInternalSelectedId(id)
                  onSelectEdge?.(id)
                  onResolveEdgeEvidence?.(edge)
                }}
                resolveNodeLabel={resolveNodeLabel}
                resolveNodeTitle={resolveNodeTitle}
              />
            </li>
          ))}
        </ul>
        {complete ? null : (
          <div className="mt-space-md flex flex-wrap items-center gap-space-sm">
            <span
              className="break-words font-label-sm text-label-sm text-on-surface-variant"
              aria-live="polite"
            >
              Đã tải {state.edges.length}/{state.totalCount} quan hệ
              {state.hasMore ? ' · Danh sách chưa tải hết' : ''}
            </span>
            {state.hasMore && state.nextCursor ? (
              <button
                className="inline-flex items-center gap-space-xs rounded-full border border-brand-500/70 bg-white px-space-md py-space-xs font-body-sm text-body-sm font-semibold text-on-surface shadow-sm hover:bg-brand-500/5 disabled:opacity-60 focus-visible:outline focus-visible:outline-2"
                disabled={!onLoadPage || loading}
                onClick={loadNextPage}
                type="button"
              >
                <MaterialIcon name="expand_more" className="text-[18px]" />
                {loading ? 'Đang tải quan hệ…' : 'Tải thêm quan hệ'}
              </button>
            ) : (
              <span
                className="font-body-sm text-body-sm text-error"
                role="status"
              >
                {state.paginationError ??
                  'Số quan hệ đã nhận chưa khớp tổng số từ máy chủ.'}
              </span>
            )}
            {loadError ? (
              <p
                className="w-full font-body-sm text-body-sm text-error"
                role="alert"
              >
                Không tải được trang tiếp theo. Thử lại để tiếp tục danh sách.
              </p>
            ) : null}
          </div>
        )}
      </section>
      <div className="min-w-0 lg:sticky lg:top-0">
        {selectedEdge ? (
          <RelationInspector
            edge={selectedEdge}
            showLabel={showLabel}
            onOpenEvidence={onOpenEvidence}
            evidenceOpen={evidenceEdgeId === selectedEdge.id}
            resolveNodeLabel={resolveNodeLabel}
            resolveNodeTitle={resolveNodeTitle}
          />
        ) : (
          <div className="flex flex-col items-center gap-space-xs rounded-lg bg-surface-container-low px-space-lg py-space-xl text-center font-body-sm text-body-sm text-on-surface-variant">
            <MaterialIcon
              name="ads_click"
              className="text-[28px] text-outline"
            />
            Chọn một quan hệ để xem hai điều khoản liên quan.
          </div>
        )}
      </div>
    </div>
  )
}

function RelationRow({
  edge,
  selected,
  onSelect,
  resolveNodeLabel = (nodeId) => `Mã điều khoản ${nodeId}`,
  resolveNodeTitle,
  showLabel = true,
}: {
  edge: ContractGraphEdge
  selected: boolean
  onSelect: (id: string) => void
  showLabel?: boolean
  resolveNodeLabel?: NodeLabelResolver
  resolveNodeTitle?: NodeLabelResolver
}) {
  const sourceText = resolveNodeLabel(
    edge.source_node_id,
    edge.source_document_id,
  )
  const targetText = [
    resolveNodeLabel(edge.target_node_id, edge.target_document_id),
    edge.target_address,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <button
      aria-pressed={selected}
      aria-controls={selected ? 'ai2-selected-relation-detail' : undefined}
      className={`w-full min-w-0 rounded-lg border px-space-md py-space-sm text-left transition-colors focus-visible:outline focus-visible:outline-2 ${
        selected
          ? 'border-brand-300 bg-brand-50'
          : 'border-outline-variant/30 bg-surface-container-lowest hover:bg-surface-container-low'
      }`}
      onClick={() => onSelect(edge.id)}
      type="button"
    >
      <span className="flex flex-wrap items-center gap-space-xs">
        {showLabel ? <RelationBadge label={edge.label} /> : null}
        <ReviewBadge state={edge.review_state} />
      </span>
      <span className="mt-space-xs grid min-w-0 gap-space-xs font-body-sm text-body-sm sm:grid-cols-[1fr_auto_1fr] sm:items-start">
        <ClauseSummary
          title={resolveNodeTitle?.(
            edge.source_node_id,
            edge.source_document_id,
          )}
          text={sourceText}
        />
        <MaterialIcon
          name={edge.directed ? 'arrow_forward' : 'sync_alt'}
          className="hidden pt-0.5 text-[18px] text-outline sm:block"
        />
        <ClauseSummary
          title={resolveNodeTitle?.(
            edge.target_node_id,
            edge.target_document_id,
          )}
          text={targetText}
        />
      </span>
    </button>
  )
}

function ClauseSummary({ title, text }: { title?: string; text: string }) {
  return (
    <span className="flex min-w-0 flex-col" title={text}>
      {title ? (
        <span className="truncate font-semibold text-on-surface">{title}</span>
      ) : null}
      <span
        className={`line-clamp-2 break-words ${title ? 'text-on-surface-variant' : 'text-on-surface'}`}
      >
        {text}
      </span>
    </span>
  )
}
