import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getContractGraphPage, getProcessingTrace } from './contractGraph'
import { getJson } from './client'

vi.mock('./client', () => ({ getJson: vi.fn() }))

const edge = {
  id: 'pair-1',
  kind: 'PAIR',
  label: 'REFERENCE',
  directed: false,
  source_node_id: 'node-a',
  target_node_id: 'node-b',
  review_state: 'NEEDS_REVIEW',
  source_citation_ref: 'cite:a',
  target_citation_ref: 'cite:b',
  digest: 'edge-digest',
  source_document_id: 'doc-a',
  target_document_id: 'doc-b',
}

describe('contract graph API client', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches only the Backend graph route and validates job and snapshot identity', async () => {
    vi.mocked(getJson).mockImplementation(
      async () =>
        ({
          job_id: 'job-a',
          snapshot_digest: 'digest-a',
          graph_kind: 'pair',
          status: 'READY',
          edges: [edge],
          total_count: 1,
          has_more: false,
          next_cursor: null,
        }) as never,
    )

    const page = await getContractGraphPage({
      dossierId: 'dossier/a',
      jobId: 'job-a',
      snapshotDigest: 'digest-a',
      graphKind: 'pair',
      cursor: 'opaque-cursor',
    })

    expect(page.edges[0]?.label).toBe('REFERENCE')
    expect(page.edges[0]?.source_document_id).toBe('doc-a')
    const path = vi.mocked(getJson).mock.calls[0]?.[0]
    expect(path).toContain(
      '/api/v1/dossiers/dossier%2Fa/ai2/contract-graph/pair?',
    )
    expect(path).toContain('cursor=opaque-cursor')
  })

  it('rejects a page from another digest and unknown status', async () => {
    vi.mocked(getJson).mockImplementation(
      async () =>
        ({
          job_id: 'job-a',
          snapshot_digest: 'old-digest',
          graph_kind: 'pair',
          status: 'READY',
          edges: [edge],
          total_count: 1,
          has_more: false,
          next_cursor: null,
        }) as never,
    )
    await expect(
      getContractGraphPage({
        dossierId: 'dossier-a',
        jobId: 'job-a',
        snapshotDigest: 'digest-a',
        graphKind: 'pair',
      }),
    ).rejects.toThrow('identity or status mismatch')

    vi.mocked(getJson).mockImplementation(
      async () =>
        ({
          job_id: 'job-a',
          snapshot_digest: 'digest-a',
          graph_kind: 'pair',
          status: 'MAGIC',
          edges: [],
          total_count: 0,
          has_more: false,
          next_cursor: null,
        }) as never,
    )
    await expect(
      getContractGraphPage({
        dossierId: 'dossier-a',
        jobId: 'job-a',
        snapshotDigest: 'digest-a',
        graphKind: 'pair',
      }),
    ).rejects.toThrow('identity or status mismatch')
  })

  it('rejects graph edges without endpoint document provenance keys', async () => {
    const edgeWithoutSourceDocument: Record<string, unknown> = { ...edge }
    delete edgeWithoutSourceDocument.source_document_id
    vi.mocked(getJson).mockImplementation(
      async () =>
        ({
          job_id: 'job-a',
          snapshot_digest: 'digest-a',
          graph_kind: 'pair',
          status: 'READY',
          edges: [edgeWithoutSourceDocument],
          total_count: 1,
          has_more: false,
          next_cursor: null,
        }) as never,
    )
    await expect(
      getContractGraphPage({
        dossierId: 'dossier-a',
        jobId: 'job-a',
        snapshotDigest: 'digest-a',
        graphKind: 'pair',
      }),
    ).rejects.toThrow('invalid source document')
  })

  it('validates processing trace state and scope', async () => {
    vi.mocked(getJson).mockImplementation(
      async () =>
        ({
          job_id: 'job-a',
          schema_version: 'ai2.processing-trace.v1',
          snapshot_digest: 'digest-a',
          status: 'INCOMPLETE_UNKNOWN',
          trace_status: 'AVAILABLE',
          stages: [
            {
              stage_id: 'contract_graph_operation',
              status: 'INCOMPLETE_UNKNOWN',
              started_ms: 10,
              duration_ms: null,
              item_count: null,
              reason_code: 'TERMINAL_WITH_OPEN_STAGE',
            },
          ],
        }) as never,
    )

    const trace = await getProcessingTrace({
      dossierId: 'dossier-a',
      jobId: 'job-a',
      snapshotDigest: 'digest-a',
    })

    expect(trace.status).toBe('INCOMPLETE_UNKNOWN')
    expect(trace.stages[0]?.reason_code).toBe('TERMINAL_WITH_OPEN_STAGE')
  })

  it('preserves job outcome from Backend trace metadata', async () => {
    vi.mocked(getJson).mockResolvedValue({
      job_id: 'job-a',
      schema_version: 'ai2.processing-trace.v1',
      snapshot_digest: 'digest-a',
      status: 'COMPLETE',
      trace_status: 'AVAILABLE',
      execution_id: 'execution-a',
      job_status: 'SUCCEEDED',
      stages: [
        {
          stage_id: 'contract_graph_pairs',
          status: 'COMPLETED',
          started_ms: 10,
          duration_ms: 4,
          item_count: 1,
          reason_code: null,
        },
      ],
    } as never)

    const trace = await getProcessingTrace({
      dossierId: 'dossier-a',
      jobId: 'job-a',
      snapshotDigest: 'digest-a',
    })

    expect(trace.status).toBe('COMPLETE')
    expect(trace.job_status).toBe('SUCCEEDED')
    expect(trace.stages[0]?.stage_id).toBe('contract_graph_pairs')
    expect(trace).not.toHaveProperty('execution_id')
  })

  it('preserves a failed job even when its trace stages are terminal', async () => {
    vi.mocked(getJson).mockResolvedValue({
      job_id: 'job-a',
      schema_version: 'ai2.processing-trace.v1',
      snapshot_digest: 'digest-a',
      status: 'COMPLETE',
      trace_status: 'AVAILABLE',
      job_status: 'FAILED',
      stages: [],
    } as never)
    const trace = await getProcessingTrace({
      dossierId: 'dossier-a',
      jobId: 'job-a',
      snapshotDigest: 'digest-a',
    })
    expect(trace.status).toBe('COMPLETE')
    expect(trace.job_status).toBe('FAILED')
  })

  it('preserves cancellation as a terminal job outcome', async () => {
    vi.mocked(getJson).mockResolvedValue({
      job_id: 'job-a',
      schema_version: 'ai2.processing-trace.v1',
      snapshot_digest: 'digest-a',
      status: 'COMPLETE',
      trace_status: 'AVAILABLE',
      job_status: 'CANCELLED',
      stages: [],
    } as never)
    const trace = await getProcessingTrace({
      dossierId: 'dossier-a',
      jobId: 'job-a',
      snapshotDigest: 'digest-a',
    })
    expect(trace.job_status).toBe('CANCELLED')
  })
})
