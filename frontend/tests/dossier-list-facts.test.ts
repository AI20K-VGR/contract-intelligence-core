import { beforeEach, describe, expect, it, vi } from 'vitest'

const { requestJson } = vi.hoisted(() => ({ requestJson: vi.fn() }))

vi.mock('../src/api/client', async () => {
  const actual =
    await vi.importActual<typeof import('../src/api/client')>(
      '../src/api/client',
    )
  return { ...actual, requestJson }
})

const {
  inspectionFromContractOcr,
  listDossiers,
  listedDossierFacts,
  normalizeDossierSummary,
} = await import('../src/api/dossiers')

const OCR = {
  document_id: 'doc_1',
  filename: 'hop-dong.pdf',
  page_count: 3,
  failed_pages: 0,
  first_error: null,
}

function row(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    name: `Hồ sơ ${id}`,
    latest_job_status: 'pending_review',
    created_at: '2026-10-19T00:00:00Z',
    ...extra,
  }
}

describe('normalizeDossierSummary (v3.3.0, #144)', () => {
  it('reads document_counts and contract_ocr from the list item', () => {
    const summary = normalizeDossierSummary(
      row('d1', {
        document_counts: { contracts: 1, annexes: 2 },
        contract_ocr: OCR,
      }),
    )
    expect(summary?.document_counts).toEqual({ contracts: 1, annexes: 2 })
    expect(summary?.contract_ocr).toEqual(OCR)
  })

  it('keeps null (no permission) apart from a missing field (older backend)', () => {
    const denied = normalizeDossierSummary(
      row('d1', { document_counts: null, contract_ocr: null }),
    )
    expect(denied?.document_counts).toBeNull()
    expect(denied?.contract_ocr).toBeNull()
    const older = normalizeDossierSummary(row('d2'))
    expect(older).not.toHaveProperty('document_counts')
    expect(older).not.toHaveProperty('contract_ocr')
  })
})

describe('inspectionFromContractOcr (#144)', () => {
  it('reads like the per-page inspection it replaces', () => {
    expect(inspectionFromContractOcr('pending_review', OCR).state).toBe('done')
    expect(inspectionFromContractOcr('processing', OCR).state).toBe('running')
    // Chưa có trang nào: theo trạng thái job.
    const empty = { ...OCR, page_count: 0 }
    expect(inspectionFromContractOcr('processing', empty).state).toBe('running')
    expect(inspectionFromContractOcr('failed', empty).state).toBe('error')
    expect(inspectionFromContractOcr('uploaded', null).state).toBe('pending')
  })

  it('reports a failed page with the Vietnamese message and the raw error', () => {
    const inspection = inspectionFromContractOcr('extracted', {
      ...OCR,
      failed_pages: 1,
      first_error: 'APIConnectionError: Connection error.',
    })
    expect(inspection.state).toBe('error')
    expect(inspection.detail).toBe(
      'Mất kết nối khi đọc tài liệu. Vui lòng bấm "Đọc lại".',
    )
    expect(inspection.technical).toContain('APIConnectionError')
  })
})

describe('listedDossierFacts (#144)', () => {
  it('covers every dossier whose list item carries the fields', () => {
    const summaries = [
      row('d1', {
        document_counts: { contracts: 1, annexes: 0 },
        contract_ocr: OCR,
      }),
      row('d2', { document_counts: null, contract_ocr: null }),
      row('d3'),
    ].map((item) => normalizeDossierSummary(item)!)
    const facts = listedDossierFacts(summaries)
    expect(facts.counts).toEqual({ d1: { contracts: 1, annexes: 0 }, d2: null })
    expect(Object.keys(facts.ocr)).toEqual(['d1', 'd2'])
    // d3: backend cũ, trang vẫn gọi /documents như trước.
    expect(facts.counts).not.toHaveProperty('d3')
  })
})

describe('dossier list requests (#144)', () => {
  beforeEach(() => requestJson.mockReset())

  it('loads N dossiers with counts and OCR state in one request', async () => {
    const items = Array.from({ length: 20 }, (_, index) =>
      row(`d${index}`, {
        document_counts: { contracts: 1, annexes: 2 },
        contract_ocr: OCR,
      }),
    )
    requestJson.mockResolvedValueOnce({ data: items, meta: { total: 20 } })
    const result = await listDossiers({ limit: 100, offset: 0 })
    const facts = listedDossierFacts(result.items)
    expect(Object.keys(facts.counts)).toHaveLength(20)
    expect(Object.keys(facts.ocr)).toHaveLength(20)
    expect(requestJson).toHaveBeenCalledTimes(1)
    const paths = requestJson.mock.calls.map((call) => String(call[0]))
    expect(paths.some((path) => path.includes('/documents'))).toBe(false)
  })
})
