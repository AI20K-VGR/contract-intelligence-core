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
  const resolveNodeLabel = (nodeId: string, documentId?: string | null) =>
    `${documentId === 'body-doc' ? 'Hợp đồng gốc' : `Phụ lục ${documentId ?? 'chưa rõ'}`} · Điều ${nodeId}`

  return (
    <div className="mx-auto flex min-w-0 max-w-5xl flex-col gap-3 p-3">
      <p role="status" className="break-words text-sm">
        Dữ liệu demo tổng hợp · không gọi API · không phải kết quả AI2 từ tài liệu người dùng
      </p>
      <ProcessingTimeline trace={trace} />
      <ContractGraphCanvas
        page={page}
        selectedId={selectedId}
        onSelectEdge={setSelectedId}
        resolveNodeLabel={resolveNodeLabel}
      />
      <RelationList
        page={page}
        selectedId={selectedId}
        onSelectEdge={setSelectedId}
        onOpenCitation={(ref, node) =>
          setAction(`Bằng chứng minh họa: ${ref} · Điều ${node}`)
        }
        resolveNodeLabel={resolveNodeLabel}
      />
      <p role="status" aria-live="polite">
        {action}
      </p>
    </div>
  )
}
