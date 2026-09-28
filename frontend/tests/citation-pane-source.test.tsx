import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { CitationPane } from '../src/components/CitationPane'

describe('CitationPane page source', () => {
  it('declares that the highlight is rendered over the AI1 page preview', () => {
    const html = renderToStaticMarkup(
      <CitationPane
        documentId="doc-1"
        citeNo={1}
        node={{
          id: 'line-1',
          nodeType: 'line',
          label: 'Citation',
          number: null,
          title: null,
          text: 'Evidence',
          pageStart: 3,
          pageEnd: 3,
          confidence: null,
          regions: [{ pageNo: 3, bbox: [0.1, 0.2, 0.8, 0.3] }],
          children: [],
        }}
        onClose={() => undefined}
      />,
    )

    expect(html).toContain('data-page-source="ai1-preview"')
  })
})
