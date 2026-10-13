import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ContractGraphPage, ProcessingTrace } from '../api/contractGraph'
import { getContractGraphPage, getProcessingTrace } from '../api/contractGraph'
import { ContractGraphCanvas } from '../components/ai2-graph/ContractGraphCanvas'
import { ContentSharingConsent } from '../components/ai2-graph/ContentSharingConsent'
import { RelationList } from '../components/ai2-graph/RelationList'
import {
  AI2_GRAPH_UI_ENABLED,
  createLatestRequestGuard,
  isLegacyCitationFallbackAllowed,
  loadAi2GraphDataIfVisible,
} from '../components/ai2-graph/contractGraphRuntime'

vi.mock('../api/contractGraph', () => ({
  getContractGraphPage: vi.fn(),
  getProcessingTrace: vi.fn(),
}))

const page: ContractGraphPage = {
  job_id: 'job-a',
  snapshot_digest: 'snapshot-a',
  graph_kind: 'pair',
  status: 'READY',
  edges: [
    {
      id: 'edge-a',
      kind: 'PAIR',
      label: 'REFERENCE',
      directed: false,
      source_node_id: 'clause-a',
      target_node_id: 'clause-b',
      source_document_id: null,
      target_document_id: null,
      review_state: 'NEEDS_REVIEW',
      source_citation_ref: 'citation-a',
      target_citation_ref: 'citation-b',
      digest: 'edge-a-digest',
    },
  ],
  total_count: 3,
  has_more: true,
  next_cursor: 'cursor-2',
}
const trace: ProcessingTrace = {
  job_id: 'job-a',
  snapshot_digest: 'snapshot-a',
  status: 'COMPLETE',
  trace_status: 'AVAILABLE',
  stages: [],
}

describe('dossier AI2 graph integration', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders per-dossier content consent as an accessible, fail-closed control', () => {
    const html = renderToStaticMarkup(
      <ContentSharingConsent dossierId="dossier-a" enabled={false} onSaved={() => {}} />,
    )
    expect(html).toContain('type="checkbox"')
    expect(html).not.toContain('checked=""')
    expect(html).toContain('Cho phép AI2 xử lý nội dung hồ sơ')
    expect(html).toContain('Thay đổi có hiệu lực từ yêu cầu AI2 tiếp theo.')
  })

  it('allows legacy OCR fallback only for missing opaque citations in the same document', () => {
    expect(
      isLegacyCitationFallbackAllowed('cite:opaque', 404, 'doc-a', 'doc-a'),
    ).toBe(true)
    expect(
      isLegacyCitationFallbackAllowed('cite:opaque', 403, 'doc-a', 'doc-a'),
    ).toBe(false)
    expect(
      isLegacyCitationFallbackAllowed('cite:opaque', 503, 'doc-a', 'doc-a'),
    ).toBe(false)
    expect(
      isLegacyCitationFallbackAllowed('citation-id', 404, 'doc-a', 'doc-a'),
    ).toBe(false)
    expect(
      isLegacyCitationFallbackAllowed('cite:opaque', 404, 'doc-a', 'doc-b'),
    ).toBe(false)
    expect(
      isLegacyCitationFallbackAllowed('cite:opaque', 404, null, 'doc-a'),
    ).toBe(false)
  })

  it('renders a read-only bounded SVG page with a clear partial-result label', () => {
    const html = renderToStaticMarkup(
      <ContractGraphCanvas
        page={page}
        selectedId="edge-a"
        onSelectEdge={() => {}}
      />,
    )
    expect(html).toContain('role="group"')
    expect(html).toContain('Đang xem 1/3 quan hệ')
    expect(html).toContain('danh sách bên dưới tải theo trang')
    expect(html).toContain('REFERENCE')
    expect(html).toContain('Kéo vùng trống để di chuyển')
    expect(html).toContain('Chọn đường nối để xem chi tiết')
    expect(html).toContain('tabindex="0"')
    expect(html).toContain('aria-pressed="true"')
  })

  it('shows the amendment target address on the graph node and relation', () => {
    const addressedPage = {
      ...page,
      edges: [{ ...page.edges[0]!, target_address: 'Điều 18 khoản 5a' }],
    }
    const html = renderToStaticMarkup(
      <ContractGraphCanvas
        page={addressedPage}
        selectedId="edge-a"
        onSelectEdge={() => {}}
        resolveNodeLabel={(id) => `Phụ lục A · ${id}`}
      />,
    )
    expect(html).toContain('Phụ lục A · clause-b · Điều 18 khoản 5a')
    expect(html).toContain('địa chỉ đích Điều 18 khoản 5a')
  })

  it('enables graph by default and does not call APIs when disabled or closed', async () => {
    expect(AI2_GRAPH_UI_ENABLED).toBe(true)
    await expect(
      loadAi2GraphDataIfVisible({
        enabled: false,
        visible: true,
        dossierId: 'd',
        jobId: 'j',
        snapshotDigest: 's',
        graphKind: 'pair',
      }),
    ).resolves.toBeNull()
    await expect(
      loadAi2GraphDataIfVisible({
        enabled: true,
        visible: false,
        dossierId: 'd',
        jobId: 'j',
        snapshotDigest: 's',
        graphKind: 'pair',
      }),
    ).resolves.toBeNull()
    expect(getContractGraphPage).not.toHaveBeenCalled()
    expect(getProcessingTrace).not.toHaveBeenCalled()
  })

  it('loads trace and first graph page through the Backend client when visible and enabled', async () => {
    vi.mocked(getContractGraphPage).mockResolvedValue(page)
    vi.mocked(getProcessingTrace).mockResolvedValue(trace)
    const result = await loadAi2GraphDataIfVisible({
      enabled: true,
      visible: true,
      dossierId: 'd',
      jobId: 'j',
      snapshotDigest: 's',
      graphKind: 'pair',
    })
    expect(getContractGraphPage).toHaveBeenCalledOnce()
    expect(getProcessingTrace).toHaveBeenCalledOnce()
    expect(result?.page).toBe(page)
  })

  it('preserves the graph page when the independent trace request fails', async () => {
    vi.mocked(getContractGraphPage).mockResolvedValue(page)
    vi.mocked(getProcessingTrace).mockRejectedValue(
      new Error('trace unavailable'),
    )
    const result = await loadAi2GraphDataIfVisible({
      enabled: true,
      visible: true,
      dossierId: 'd',
      jobId: 'j',
      snapshotDigest: 's',
      graphKind: 'pair',
    })
    expect(result?.page).toBe(page)
    expect(result?.trace.status).toBe('TRACE_UNAVAILABLE')
  })

  it('preserves the processing trace when the graph request fails', async () => {
    vi.mocked(getContractGraphPage).mockRejectedValue(
      new Error('graph unavailable'),
    )
    vi.mocked(getProcessingTrace).mockResolvedValue(trace)
    const result = await loadAi2GraphDataIfVisible({
      enabled: true,
      visible: true,
      dossierId: 'd',
      jobId: 'j',
      snapshotDigest: 's',
      graphKind: 'pair',
    })
    expect(result?.graphError).toBe(true)
    expect(result?.page).toBeNull()
    expect(result?.trace).toBe(trace)
  })

  it('allows only the latest citation request to publish its response', () => {
    const requests = createLatestRequestGuard()
    const first = requests.start()
    const second = requests.start()
    expect(requests.isCurrent(first)).toBe(false)
    expect(requests.isCurrent(second)).toBe(true)
    requests.invalidate()
    expect(requests.isCurrent(second)).toBe(false)
  })

  it('records a dependency-free SVG/list spike on a scrubbed multi-annex fixture', () => {
    const edges = Array.from({ length: 30 }, (_, index) => ({
      id: `edge-${index}`,
      kind: 'PAIR' as const,
      label: ['REFERENCE', 'CONFLICT', 'GENERAL_SPECIFIC'][index % 3]!,
      directed: index % 3 !== 1,
      source_node_id: `body-clause-${index % 10}`,
      target_node_id: `annex-${index % 4}-clause-${index}`,
      source_document_id: 'body-doc',
      target_document_id: `annex-${index % 4}`,
      review_state: index % 5 === 0 ? 'NEEDS_REVIEW' : 'ACCEPTED',
      source_citation_ref: `citation-source-${index}`,
      target_citation_ref: `citation-target-${index}`,
      digest: `digest-${index}`,
    }))
    const fixturePage: ContractGraphPage = {
      ...page,
      edges,
      total_count: 250,
      has_more: true,
      next_cursor: 'cursor-next',
    }
    const resolveNodeLabel = (id: string) => id.replaceAll('-', ' ')
    const renderCanvas = () =>
      renderToStaticMarkup(
        <ContractGraphCanvas
          page={fixturePage}
          selectedId="edge-0"
          onSelectEdge={() => {}}
          resolveNodeLabel={resolveNodeLabel}
        />,
      )
    const renderList = () =>
      renderToStaticMarkup(
        <RelationList
          page={fixturePage}
          onOpenCitation={() => {}}
          resolveNodeLabel={resolveNodeLabel}
        />,
      )
    renderCanvas()
    renderList()
    const measure = (render: () => string) => {
      const start = performance.now()
      let html = ''
      for (let index = 0; index < 8; index += 1) html = render()
      return {
        eightRenderBatchMs: Number((performance.now() - start).toFixed(2)),
        bytes: new TextEncoder().encode(html).length,
      }
    }
    const canvas = measure(renderCanvas)
    const list = measure(renderList)
    console.info(
      `AI2_RENDERER_SPIKE ${JSON.stringify({ fixture: 'synthetic-multi-annex-30-edges', iterations: 8, canvas, list })}`,
    )
    expect(renderCanvas()).toContain('Đang xem 30/250 quan hệ')
    expect(renderList()).toContain('Đã tải 30/250 quan hệ')
    expect(renderList()).toContain('Danh sách chưa tải hết')
  })
})
