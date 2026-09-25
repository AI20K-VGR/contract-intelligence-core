import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Ai2SearchResult } from '../src/api/ai2'
import { DossierSearchResults } from '../src/components/DossierSearchResults'

const result: Ai2SearchResult = {
  dossierId: 'dos-1',
  query: 'Thông tin bên A',
  answer: 'Công ty ABC',
  connected: true,
  reviewState: 'ANSWERED',
  hits: [
    {
      text: 'Bên A được ghi: Công ty ABC',
      pageNo: 3,
      sourceFileId: 'doc-1',
      lineId: 'line-1',
      bbox: [0.1, 0.2, 0.3, 0.4],
      citation: {
        status: 'LOCATABLE',
        sourceFileId: 'doc-1',
        lineId: 'line-1',
        pageNo: 3,
        bbox: [0.1, 0.2, 0.3, 0.4],
        nodeId: null,
        quote: 'Bên A được ghi: Công ty ABC',
      },
    },
  ],
}

describe('DossierSearchResults', () => {
  it('renders live answer and locatable evidence instead of static copy', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <DossierSearchResults
          result={result}
          onSelectCitation={() => undefined}
        />
      </MemoryRouter>,
    )

    expect(html).toContain('Công ty ABC')
    expect(html).toContain('line-1')
    expect(html).toContain('Đã định vị nguồn')
    expect(html).not.toContain('98.4%')
  })

  it('exposes the full citation navigation scope for the live viewer', async () => {
    const { buildCitationNavigationState } =
      await import('../src/components/DossierSearchResults')
    expect(buildCitationNavigationState(result, result.hits[0], 0)).toEqual({
      dossierId: 'dos-1',
      documentId: 'doc-1',
      citationId: 'line-1',
      sourceFileId: 'doc-1',
      pageNo: 3,
      lineId: 'line-1',
      bbox: [0.1, 0.2, 0.3, 0.4],
      scope: 'body',
      status: 'LOCATABLE',
      quote: result.hits[0].citation.quote,
    })
  })
})
