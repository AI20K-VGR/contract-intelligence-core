import { useRef, useState } from 'react'

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
import { RelationInspector } from './RelationInspector'

export function RelationList({
  page,
  onLoadPage,
  onOpenCitation,
  resolveNodeLabel,
  selectedId: controlledSelectedId,
  onSelectEdge,
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
  const selected = state.edges.find((edge) => edge.id === selectedId) ?? null
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
        className="min-w-0 rounded-lg border border-outline-variant p-3"
      >
        <h2 id="ai2-relations-title" className="font-title-md font-semibold">
          Quan hệ điều khoản
        </h2>
        <p className="mt-2 break-words" role="status">
          {graphStatusLabel(state.status)}
        </p>
      </section>
    )
  }

  return (
    <section
      aria-labelledby="ai2-relations-title"
      className="min-w-0 rounded-lg border border-outline-variant p-3"
    >
      <h2 id="ai2-relations-title" className="font-title-md font-semibold">
        Quan hệ điều khoản
      </h2>
      {state.edges.length === 0 && complete ? (
        <p className="mt-2" role="status">
          Đã xác nhận: không có quan hệ
        </p>
      ) : (
        <>
          <p className="mt-1 break-words text-sm" aria-live="polite">
            Đã tải {state.edges.length}/{state.totalCount} quan hệ
            {complete
              ? ' · Đã tải đầy đủ'
              : state.hasMore
                ? ' · Danh sách chưa tải hết'
                : ' · Tổng số chưa khớp'}
          </p>
          <ul className="mt-3 flex min-w-0 flex-col gap-2">
            {state.edges.map((edge) => (
              <RelationRow
                key={edge.id}
                edge={edge}
                selected={edge.id === selectedId}
                onSelect={(id) => {
                  setInternalSelectedId(id)
                  onSelectEdge?.(id)
                }}
                resolveNodeLabel={resolveNodeLabel}
              />
            ))}
          </ul>
          {state.hasMore && state.nextCursor ? (
            <div className="mt-3">
              <button
                className="min-h-11 rounded border border-outline px-3 py-2 focus-visible:outline focus-visible:outline-2"
                disabled={!onLoadPage || loading}
                onClick={loadNextPage}
                type="button"
              >
                {loading ? 'Đang tải quan hệ…' : 'Tải thêm quan hệ'}
              </button>
              {loadError ? (
                <p className="mt-2 text-error" role="alert">
                  Không tải được trang tiếp theo. Thử lại để tiếp tục danh sách.
                </p>
              ) : null}
            </div>
          ) : !complete ? (
            <p className="mt-2 text-error" role="status">
              {state.paginationError ??
                'Số quan hệ đã nhận chưa khớp tổng số từ máy chủ.'}
            </p>
          ) : null}
          {selected ? (
            <div className="mt-3">
              <RelationInspector
                edge={selected}
                onOpenCitation={onOpenCitation}
                resolveNodeLabel={resolveNodeLabel}
              />
            </div>
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
    <li className="min-w-0">
      <button
        aria-pressed={selected}
        className="min-h-11 w-full min-w-0 rounded-md border border-outline-variant p-3 text-left focus-visible:outline focus-visible:outline-2"
        onClick={() => onSelect(edge.id)}
        type="button"
      >
        <span className="block break-words font-semibold">
          {edge.label} ·{' '}
          {edge.review_state === 'NEEDS_REVIEW'
            ? 'cần review'
            : edge.review_state}
        </span>
        <span className="mt-1 grid min-w-0 gap-1 text-sm text-on-surface-variant sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <span className="break-words">
            Nguồn:{' '}
            {resolveNodeLabel(edge.source_node_id, edge.source_document_id)}
          </span>
          <span aria-hidden="true">{edge.directed ? '→' : '↔'}</span>
          <span className="break-words">
            Đích:{' '}
            {[
              resolveNodeLabel(edge.target_node_id, edge.target_document_id),
              edge.target_address,
            ]
              .filter(Boolean)
              .join(' · ')}
          </span>
        </span>
      </button>
    </li>
  )
}
