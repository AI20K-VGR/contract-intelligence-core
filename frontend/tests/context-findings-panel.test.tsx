import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import {
  ContextFindingsPanel,
  type ContextFindingsPanelModel,
} from '../src/components/ContextFindingsPanel'

describe('ContextFindingsPanel', () => {
  it('keeps context, evidence, coverage and trace visible when facts/findings are empty', () => {
    const model: ContextFindingsPanelModel = {
      facts: [],
      findings: [],
      contextFindings: [
        {
          id: 'context-1',
          reasonCode: 'MISSING_ANNEX_MAPPING',
          subject: 'SLA appendix',
          reviewState: 'NEEDS_REVIEW',
        },
      ],
      evidenceIssues: [
        { code: 'PARTIAL_PAGE_COVERAGE', message: 'Trang 8 chưa đủ mapping.' },
      ],
      coverage: { pages: 8, covered: 7, status: 'NEEDS_REVIEW' },
      trace: [{ code: 'LEXICAL_RETRIEVAL', layer: 'bounded' }],
      reviewState: 'NEEDS_REVIEW',
    }

    const html = renderToStaticMarkup(<ContextFindingsPanel model={model} />)

    expect(html).toContain('0 dữ kiện')
    expect(html).toContain('0 phát hiện')
    expect(html).toContain('Phát hiện cần xem lại')
    expect(html).toContain('Có điểm cần kiểm tra khi phân tích hồ sơ')
    expect(html).toContain('7 / 8')
    expect(html).toContain('AI đã thực hiện 1 bước')
    expect(html).toContain('Cần rà soát')
    // Mã hệ thống không hiện nguyên văn.
    expect(html).not.toContain('MISSING_ANNEX_MAPPING')
    expect(html).not.toContain('LEXICAL_RETRIEVAL')
    expect(html).not.toContain('NEEDS_REVIEW')
  })
})
