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

    expect(html).toContain('0 facts')
    expect(html).toContain('0 findings')
    expect(html).toContain('MISSING_ANNEX_MAPPING')
    expect(html).toContain('PARTIAL_PAGE_COVERAGE')
    expect(html).toContain('7 / 8')
    expect(html).toContain('LEXICAL_RETRIEVAL')
    expect(html).toContain('NEEDS_REVIEW')
  })
})
