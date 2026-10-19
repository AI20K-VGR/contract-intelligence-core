import { useState } from 'react'

import type {
  ContractGraphPage,
  ProcessingTrace,
} from '../../api/contractGraph'
import { ContractGraphCanvas } from './ContractGraphCanvas'
import { ProcessingTimeline } from './ProcessingTimeline'
import { RelationList } from './RelationList'

const page: ContractGraphPage = {
  job_id: 'manual-job',
  snapshot_digest: 'manual-snapshot',
  graph_kind: 'pair',
  status: 'READY',
  total_count: 3,
  has_more: false,
  next_cursor: null,
  edges: [
    {
      id: 'rel-reference',
      kind: 'PAIR',
      label: 'REFERENCE',
      directed: false,
      source_node_id: '2.1',
      target_node_id: '3',
      source_document_id: 'body-doc',
      target_document_id: 'annex-1',
      review_state: 'NEEDS_REVIEW',
      source_citation_ref: 'demo:body-2-1',
      target_citation_ref: 'demo:annex-1-3',
      digest: 'demo-reference',
    },
    {
      id: 'rel-conflict',
      kind: 'PAIR',
      label: 'CONFLICT',
      directed: false,
      source_node_id: '4.2',
      target_node_id: '7',
      source_document_id: 'body-doc',
      target_document_id: 'annex-2',
      review_state: 'NEEDS_REVIEW',
      source_citation_ref: 'demo:body-4-2',
      target_citation_ref: 'demo:annex-2-7',
      digest: 'demo-conflict',
    },
    {
      id: 'rel-specific',
      kind: 'PAIR',
      label: 'GENERAL_SPECIFIC',
      directed: true,
      source_node_id: '8.1',
      target_node_id: '12',
      source_document_id: 'body-doc',
      target_document_id: 'annex-1',
      review_state: 'NEEDS_REVIEW',
      source_citation_ref: 'demo:body-8-1',
      target_citation_ref: 'demo:annex-1-12',
      digest: 'demo-specific',
    },
  ],
}

const trace: ProcessingTrace = {
  job_id: page.job_id,
  snapshot_digest: page.snapshot_digest,
  status: 'COMPLETE',
  trace_status: 'AVAILABLE',
  stages: [
    {
      stage_id: 'contract_graph_pairs',
      status: 'COMPLETED',
      started_ms: 1791720000000,
      duration_ms: 42,
      item_count: page.total_count,
      reason_code: null,
    },
  ],
}

export function ManualGraphFixture() {
  const [selectedId, setSelectedId] = useState<string | null>(
    page.edges[0]?.id ?? null,
  )
  const [action, setAction] = useState('Chưa mở bằng chứng minh họa.')
  const resolveNodeTitle = (nodeId: string, documentId?: string | null) =>
    `Điều ${nodeId} · ${documentId === 'body-doc' ? 'Hợp đồng gốc' : `Phụ lục ${documentId ?? 'chưa rõ'}`}`
  const resolveNodeLabel = (nodeId: string) =>
    `Nội dung minh họa của điều ${nodeId}: Bên A thanh toán cho Bên B trong vòng 15 ngày kể từ ngày nhận hóa đơn hợp lệ.`

  return (
    <div className="mx-auto flex min-w-0 max-w-6xl flex-col gap-3 p-3">
      <p role="status" className="break-words text-sm">
        Dữ liệu mẫu để minh họa, không phải kết quả phân tích tài liệu thật
      </p>
      <ProcessingTimeline trace={trace} />
      <ContractGraphCanvas
        page={page}
        selectedId={selectedId}
        onSelectEdge={setSelectedId}
        resolveNodeLabel={resolveNodeLabel}
        resolveNodeTitle={resolveNodeTitle}
      />
      <RelationList
        page={page}
        selectedId={selectedId}
        onSelectEdge={setSelectedId}
        onOpenEvidence={(edge) =>
          setAction(
            `Bằng chứng minh họa: ${edge.source_citation_ref} → ${edge.target_citation_ref}`,
          )
        }
        resolveNodeLabel={resolveNodeLabel}
        resolveNodeTitle={resolveNodeTitle}
      />
      <p role="status" aria-live="polite">
        {action}
      </p>
    </div>
  )
}
