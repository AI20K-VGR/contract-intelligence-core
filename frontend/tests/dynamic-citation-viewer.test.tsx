import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import {
  DynamicCitationViewer,
  type CitationViewerModel,
} from '../src/components/DynamicCitationViewer'

const annexCitation: CitationViewerModel = {
  dossierId: 'dossier-real-1',
  documentId: 'document-annex-7',
  sourceFileId: 'document-annex-7',
  citationId: 'citation-annex-42',
  scope: 'annex',
  status: 'LOCATABLE',
  quote: 'Điều kiện tại Phụ lục A được áp dụng riêng cho dịch vụ mở rộng.',
  pageNo: 7,
  lineId: 'line:annex-7:p007:l004',
  bbox: [0.1, 0.2, 0.8, 0.3],
  documentName: 'phu-luc-a.pdf',
  documentRole: 'annex',
}

describe('DynamicCitationViewer', () => {
  it('renders the selected dossier/document/source citation and annex location', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <DynamicCitationViewer citation={annexCitation} />
      </MemoryRouter>,
    )

    expect(html).toContain('dossier-real-1')
    expect(html).toContain('document-annex-7')
    expect(html).toContain('citation-annex-42')
    expect(html).toContain('Phụ lục')
    expect(html).toContain('Trang 7')
    expect(html).toContain('line:annex-7:p007:l004')
    expect(html).toContain('0.1, 0.2, 0.8, 0.3')
    expect(html).not.toContain('DOS-2024-884')
    expect(html).not.toContain('v3.2')
  })

  it('shows an unresolved gap without presenting a verified source link', () => {
    const html = renderToStaticMarkup(
      <DynamicCitationViewer
        citation={{
          ...annexCitation,
          status: 'UNRESOLVED',
          sourceFileId: null,
          documentId: null,
          pageNo: null,
          lineId: null,
          bbox: null,
        }}
      />,
    )

    expect(html).toContain('Chưa định vị được nguồn')
    expect(html).toContain('Khoảng trống evidence')
    expect(html).not.toContain('Mở nguồn đã xác minh')
  })
})
