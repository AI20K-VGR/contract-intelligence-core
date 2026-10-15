import type {
  ContractGraphEdge,
  ContractGraphPage,
  ContractGraphStatus,
} from '../../api/contractGraph'

export type RelationListState = {
  jobId: string
  snapshotDigest: string
  graphKind: ContractGraphPage['graph_kind']
  status: ContractGraphStatus
  edges: ContractGraphEdge[]
  totalCount: number
  hasMore: boolean
  nextCursor: string | null
  paginationError: string | null
}

export function createRelationListState(
  page: ContractGraphPage,
): RelationListState {
  return {
    jobId: page.job_id,
    snapshotDigest: page.snapshot_digest,
    graphKind: page.graph_kind,
    status: page.status,
    edges: dedupeEdges(page.edges),
    totalCount: page.total_count,
    hasMore: page.has_more,
    nextCursor: page.next_cursor,
    paginationError: null,
  }
}

export function appendRelationPage(
  current: RelationListState,
  page: ContractGraphPage,
  requestedCursor?: string,
): RelationListState {
  if (
    page.job_id !== current.jobId ||
    page.snapshot_digest !== current.snapshotDigest ||
    page.graph_kind !== current.graphKind
  ) {
    throw new TypeError('Relation page belongs to a different graph snapshot')
  }
  const repeatedCursor =
    requestedCursor !== undefined &&
    page.has_more &&
    page.next_cursor === requestedCursor
  return {
    ...current,
    status: page.status,
    edges: dedupeEdges([...current.edges, ...page.edges]),
    totalCount: page.total_count,
    hasMore: page.has_more && !repeatedCursor,
    nextCursor: repeatedCursor ? null : page.next_cursor,
    paginationError: repeatedCursor
      ? 'Máy chủ trả lại cursor đã dùng; dừng tải để tránh lặp trang.'
      : null,
  }
}

export function isRelationListComplete(state: RelationListState): boolean {
  return (
    state.status === 'READY' &&
    !state.hasMore &&
    state.nextCursor === null &&
    state.paginationError === null &&
    state.edges.length === state.totalCount
  )
}

export function graphStatusLabel(status: ContractGraphStatus): string {
  switch (status) {
    case 'READY':
      return 'Quan hệ đã lưu'
    case 'PENDING':
      return 'Đang xử lý quan hệ'
    case 'STALE':
      return 'Quan hệ thuộc phiên bản tài liệu cũ'
    case 'UNAVAILABLE':
      return 'Kho quan hệ hiện không khả dụng'
    case 'PERSISTENCE_UNKNOWN':
      return 'Chưa xác minh được trạng thái lưu quan hệ'
    case 'PERSIST_FAILED':
      return 'Không lưu được quan hệ'
    case 'SKIPPED':
      return 'AI2 đã bỏ qua bước tạo quan hệ'
    case 'FAILED':
      return 'Bước tạo quan hệ thất bại'
  }
}

function dedupeEdges(edges: ContractGraphEdge[]): ContractGraphEdge[] {
  const unique = new Map<string, ContractGraphEdge>()
  for (const edge of edges) if (!unique.has(edge.id)) unique.set(edge.id, edge)
  return [...unique.values()]
}
