import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type {
  ContractGraphEdge,
  ContractGraphPage,
  ProcessingTrace,
} from '../../api/contractGraph'
import { ContractGraphCanvas } from './ContractGraphCanvas'
import { ProcessingTimeline } from './ProcessingTimeline'
import { processingTimelineOutcome, stageReasonText } from './timelineOutcome'
import { RelationList } from './RelationList'
import { ManualGraphFixture } from './ManualGraphFixture'
import {
  appendRelationPage,
  createRelationListState,
  graphStatusLabel,
  isRelationListComplete,
} from './contractGraphViewModel'

const edge = (id: string): ContractGraphEdge => ({
  id,
  kind: 'PAIR' as const,
  label: 'REFERENCE',
  directed: false,
  source_node_id: `source-${id}`,
  target_node_id: `target-${id}`,
  source_document_id: null,
  target_document_id: null,
  target_address: null,
  review_state: 'NEEDS_REVIEW',
  source_citation_ref: `source-cite-${id}`,
  target_citation_ref: `target-cite-${id}`,
  digest: `digest-${id}`,
})

const page = (
  edges: ReturnType<typeof edge>[],
  cursor: string | null,
): ContractGraphPage => ({
  job_id: 'job-a',
  snapshot_digest: 'snapshot-a',
  graph_kind: 'pair',
  status: 'READY',
  edges,
  total_count: 3,
  has_more: cursor !== null,
  next_cursor: cursor,
})

const trace: ProcessingTrace = {
  job_id: 'job-a',
  snapshot_digest: 'snapshot-a',
  status: 'INCOMPLETE_UNKNOWN',
  trace_status: 'AVAILABLE',
  stages: [
    {
      stage_id: 'contract_graph_operation',
      status: 'INCOMPLETE_UNKNOWN',
      started_ms: 1791720000000,
      duration_ms: null,
      item_count: null,
      reason_code: 'TERMINAL_WITH_OPEN_STAGE',
    },
  ],
}

describe('AI2 graph accessible views', () => {
  it('renders the standalone manual fixture without using Backend API reads', () => {
    const html = renderToStaticMarkup(<ManualGraphFixture />)

    expect(html).toContain('Dữ liệu mẫu để minh họa')
    expect(html).toContain('Các bước phân tích')
    expect(html).toContain('Sơ đồ quan hệ')
    expect(html).toContain('Dẫn chiếu')
    expect(html).toContain('Có thể mâu thuẫn')
    expect(html).toContain('Quy định chung – riêng')
    expect(html).toContain('Hợp đồng gốc')
    expect(html).toContain('Phụ lục')
    expect(html).toContain('Điều 2.1 · Hợp đồng gốc')
    expect(html).not.toContain('1970')
  })

  it('keeps same node IDs distinct across source documents', () => {
    const crossDocumentPage = page(
      [
        {
          ...edge('one'),
          source_node_id: 'clause-1',
          source_document_id: 'doc-a',
        },
        {
          ...edge('two'),
          source_node_id: 'clause-1',
          source_document_id: 'doc-b',
        },
      ],
      null,
    )
    const html = renderToStaticMarkup(
      <ContractGraphCanvas
        page={crossDocumentPage}
        selectedId={null}
        onSelectEdge={() => {}}
        resolveNodeLabel={(nodeId, documentId) => `${documentId}:${nodeId}`}
      />,
    )
    expect(html).toContain('doc-a:clause-1')
    expect(html).toContain('doc-b:clause-1')
  })

  it('shows one empty state for an empty graph whatever its status, naming only real problems', () => {
    const empty = (status: ContractGraphPage['status']) =>
      renderToStaticMarkup(
        <ContractGraphCanvas
          page={{ ...page([], null), total_count: 0, status }}
          selectedId={null}
          onSelectEdge={() => {}}
        />,
      )
    const skipped = empty('SKIPPED')
    expect(skipped).toContain('Chưa tìm thấy quan hệ nào giữa các điều khoản')
    expect(skipped).not.toContain('Đã bỏ qua bước tìm quan hệ')
    expect(skipped).not.toContain('role="group"')
    expect(empty('PERSIST_FAILED')).toContain('Không lưu được quan hệ')
  })

  it('does not merge repeated node IDs when endpoint document identity is missing', () => {
    const unknownDocumentPage = page(
      [
        { ...edge('one'), source_node_id: 'clause-1' },
        { ...edge('two'), source_node_id: 'clause-1' },
      ],
      null,
    )
    const html = renderToStaticMarkup(
      <ContractGraphCanvas
        page={unknownDocumentPage}
        selectedId={null}
        onSelectEdge={() => {}}
      />,
    )
    expect(html.match(/aria-label="Mã điều khoản clause-1"/g)).toHaveLength(2)
  })

  it('keeps the target document label when an operation has a target address', () => {
    const addressed = page(
      [
        {
          ...edge('target'),
          target_document_id: 'annex-file',
          target_address: 'Điều 18 khoản 5a',
        },
      ],
      null,
    )
    const html = renderToStaticMarkup(
      <RelationList
        page={addressed}
        onOpenCitation={() => {}}
        resolveNodeLabel={(nodeId, documentId) => `${documentId}:${nodeId}`}
      />,
    )
    expect(html).toContain('annex-file:target-target · Điều 18 khoản 5a')
  })

  it('keeps an interrupted trace distinct from a successful or unavailable trace', () => {
    const html = renderToStaticMarkup(<ProcessingTimeline trace={trace} />)
    expect(html).toContain('Chưa rõ kết quả')
    expect(html).toContain('bước này chưa ghi nhận kết thúc')
    expect(html).not.toContain('Hoàn tất xử lý AI2')
  })

  it('shows only the stage that feeds the selected graph tab', () => {
    const both = {
      ...trace,
      stages: [
        { ...trace.stages[0]!, stage_id: 'contract_graph_operation' },
        { ...trace.stages[0]!, stage_id: 'contract_graph_pairs' },
      ],
    }
    const pair = renderToStaticMarkup(
      <ProcessingTimeline trace={both} graphKind="pair" />,
    )
    const operation = renderToStaticMarkup(
      <ProcessingTimeline trace={both} graphKind="operation" />,
    )
    expect(pair).toContain('Phân tích quan hệ giữa các điều khoản')
    expect(pair).not.toContain('Nối điều khoản sửa đổi với điều khoản gốc')
    expect(operation).toContain('Nối điều khoản sửa đổi với điều khoản gốc')
    expect(operation).not.toContain('Phân tích quan hệ giữa các điều khoản')
  })

  it('names the extraction and semantic stages and keeps them off both graph tabs', () => {
    const withAi2Stages = {
      ...trace,
      stages: [
        { ...trace.stages[0]!, stage_id: 'extraction' },
        { ...trace.stages[0]!, stage_id: 'semantic' },
        { ...trace.stages[0]!, stage_id: 'contract_graph_pairs' },
      ],
    }
    const pair = renderToStaticMarkup(
      <ProcessingTimeline trace={withAi2Stages} graphKind="pair" />,
    )
    const operation = renderToStaticMarkup(
      <ProcessingTimeline trace={withAi2Stages} graphKind="operation" />,
    )
    const all = renderToStaticMarkup(
      <ProcessingTimeline trace={withAi2Stages} />,
    )
    for (const html of [pair, operation]) {
      expect(html).not.toContain('Trích xuất dữ kiện')
      expect(html).not.toContain('Phân tích ngữ nghĩa')
    }
    expect(all).toContain('Trích xuất dữ kiện')
    expect(all).toContain('Phân tích ngữ nghĩa')
    expect(all).not.toContain('extraction')
    expect(all).not.toContain('semantic')
  })

  it('explains stage reason codes in plain words and never shows the code', () => {
    const html = renderToStaticMarkup(
      <ProcessingTimeline
        trace={{
          ...trace,
          status: 'COMPLETE',
          job_status: 'SUCCEEDED',
          stages: [
            {
              ...trace.stages[0]!,
              stage_id: 'contract_graph_pairs',
              status: 'COMPLETED',
              item_count: 0,
              reason_code: 'RULE_ONLY_LLM_UNAVAILABLE',
            },
          ],
        }}
      />,
    )
    expect(html).toContain('Dịch vụ AI tạm thời chưa sẵn sàng')
    expect(html).toContain('Không tìm thấy quan hệ nào')
    expect(html).not.toContain('RULE_ONLY')
    expect(html).not.toContain('Mã trạng thái')
  })

  it('shows nothing for an unknown reason code', () => {
    expect(stageReasonText('SOMETHING_NEW')).toBeNull()
    expect(stageReasonText(null)).toBeNull()
  })

  it('keeps job outcome separate from a failed enrichment stage', () => {
    const html = renderToStaticMarkup(
      <ProcessingTimeline
        trace={{
          ...trace,
          status: 'COMPLETE',
          job_status: 'FAILED',
          stages: [
            { ...trace.stages[0]!, status: 'COMPLETED', reason_code: null },
          ],
        }}
      />,
    )
    const failedStageTrace = {
      ...trace,
      status: 'COMPLETE' as const,
      stages: [{ ...trace.stages[0]!, status: 'FAILED' as const }],
    }
    expect(
      processingTimelineOutcome({ ...failedStageTrace, job_status: 'FAILED' }),
    ).toBe('job-failed')
    expect(
      processingTimelineOutcome({
        ...failedStageTrace,
        job_status: 'CANCELLED',
      }),
    ).toBe('job-cancelled')
    expect(
      processingTimelineOutcome({ ...failedStageTrace, job_status: 'RUNNING' }),
    ).toBe('job-running')
    expect(
      processingTimelineOutcome({
        ...failedStageTrace,
        job_status: 'SUCCEEDED',
      }),
    ).toBe('job-succeeded-with-stage-failure')
    expect(
      processingTimelineOutcome({
        ...failedStageTrace,
        job_status: 'SUCCEEDED',
        stages: [{ ...failedStageTrace.stages[0]!, status: 'COMPLETED' }],
      }),
    ).toBe('job-succeeded')
    expect(html).toContain('role="status"')
  })

  it('does not call a rule-only run complete, and judges each tab on its own stage', () => {
    const ruleOnlyPairs = {
      ...trace,
      status: 'COMPLETE' as const,
      job_status: 'SUCCEEDED' as const,
      stages: [
        {
          ...trace.stages[0]!,
          stage_id: 'contract_graph_operation',
          status: 'COMPLETED' as const,
          reason_code: null,
        },
        {
          ...trace.stages[0]!,
          stage_id: 'contract_graph_pairs',
          status: 'COMPLETED' as const,
          reason_code: 'RULE_ONLY_LLM_UNAVAILABLE',
        },
      ],
    }
    expect(processingTimelineOutcome(ruleOnlyPairs)).toBe(
      'job-succeeded-limited',
    )
    const pair = renderToStaticMarkup(
      <ProcessingTimeline trace={ruleOnlyPairs} graphKind="pair" />,
    )
    const operation = renderToStaticMarkup(
      <ProcessingTimeline trace={ruleOnlyPairs} graphKind="operation" />,
    )
    expect(pair).toContain('Xong, kết quả chưa đầy đủ')
    expect(pair).not.toContain('Phân tích hoàn tất')
    expect(operation).toContain('Phân tích hoàn tất')
  })

  it('distinguishes a verified empty graph from failed or unavailable persistence', () => {
    const empty = renderToStaticMarkup(
      <RelationList
        page={{ ...page([], null), total_count: 0 }}
        onOpenCitation={() => {}}
      />,
    )
    const failed = renderToStaticMarkup(
      <RelationList
        page={{ ...page([], null), total_count: 0, status: 'PERSIST_FAILED' }}
        onOpenCitation={() => {}}
      />,
    )
    expect(empty).toContain('Đã xác nhận: không có quan hệ')
    expect(failed).toContain('Không lưu được quan hệ')
  })

  it('shows incomplete paging and accessible evidence controls', () => {
    const html = renderToStaticMarkup(
      <RelationList
        page={page([edge('one')], 'cursor-2')}
        onOpenCitation={() => {}}
      />,
    )
    expect(html).toContain('Đã tải 1/3 quan hệ')
    expect(html).toContain('Danh sách chưa tải hết')
    expect(html).toContain('Tải thêm quan hệ')
    expect(html).toContain('Mở bằng chứng nguồn')
    expect(html).toContain('cần rà soát')
  })

  it('appends three pages without duplicates and is complete only after the final count matches', () => {
    let state = createRelationListState(page([edge('one')], 'cursor-2'))
    expect(isRelationListComplete(state)).toBe(false)
    state = appendRelationPage(
      state,
      page([edge('one'), edge('two')], 'cursor-3'),
      'cursor-2',
    )
    expect(state.edges.map((item) => item.id)).toEqual(['one', 'two'])
    expect(isRelationListComplete(state)).toBe(false)
    state = appendRelationPage(state, page([edge('three')], null), 'cursor-3')
    expect(state.edges.map((item) => item.id)).toEqual(['one', 'two', 'three'])
    expect(isRelationListComplete(state)).toBe(true)
  })

  it('does not repeat a cursor or mark a count mismatch as complete', () => {
    const state = appendRelationPage(
      createRelationListState(page([edge('one')], 'cursor-2')),
      page([edge('two')], 'cursor-2'),
      'cursor-2',
    )
    expect(state.nextCursor).toBeNull()
    expect(state.paginationError).toContain('cursor đã dùng')
    expect(isRelationListComplete(state)).toBe(false)
  })

  it('does not report complete when a repeated cursor happens to reach the total count', () => {
    const state = appendRelationPage(
      createRelationListState(page([edge('one')], 'cursor-2')),
      page([edge('two'), edge('three')], 'cursor-2'),
      'cursor-2',
    )
    expect(state.edges).toHaveLength(3)
    expect(state.paginationError).toBeTruthy()
    expect(isRelationListComplete(state)).toBe(false)
  })

  it('requires the next cursor to be absent before reporting complete', () => {
    const inconsistentPage = {
      ...page([edge('one'), edge('two'), edge('three')], 'cursor-2'),
      has_more: false,
    }
    expect(
      isRelationListComplete(createRelationListState(inconsistentPage)),
    ).toBe(false)
  })

  it('gives distinct text for every graph status and trace outcome', () => {
    const statuses = [
      'READY',
      'PENDING',
      'STALE',
      'UNAVAILABLE',
      'PERSISTENCE_UNKNOWN',
      'PERSIST_FAILED',
      'SKIPPED',
    ] as const
    expect(new Set(statuses.map(graphStatusLabel)).size).toBe(statuses.length)
    const outcomes = [
      'COMPLETE',
      'IN_PROGRESS',
      'INTERRUPTED_UNKNOWN',
      'INCOMPLETE_UNKNOWN',
      'TRACE_UNAVAILABLE',
    ] as const
    const labels = outcomes.map((status) =>
      renderToStaticMarkup(<ProcessingTimeline trace={{ ...trace, status }} />),
    )
    expect(new Set(labels).size).toBe(outcomes.length)
  })
})
