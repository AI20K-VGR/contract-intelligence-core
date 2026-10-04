import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { buildNumberedTree } from '../src/structure'
import {
  citationTableBbox,
  citationNode,
  citationNumbers,
  searchCites,
} from '../src/structure/citations'
import type { OcrLine } from '../src/structure/types'
import { CitedAnswer } from '../src/components/CitedAnswer'

function line(pageNo: number, lineNo: number, text: string): OcrLine {
  return {
    id: `p${pageNo}-l${lineNo}`,
    pageNo,
    lineNo,
    text,
    bbox: null,
    pageWidth: 595,
    pageHeight: 842,
  }
}

describe('citation mapping', () => {
  it('uses the cited OCR line before repeated answer text', () => {
    const nodes = buildNumberedTree([
      line(2, 1, 'Điều 1. Định nghĩa và giải thích'),
      line(2, 2, '1.1. Hệ thống gồm phần mềm và các phụ lục.'),
      line(2, 3, 'Điều 2. Phạm vi công việc'),
      line(2, 4, '2.1. Các hạng mục ngoài phạm vi chỉ được thực hiện tại phụ lục 1.'),
    ])
    const cites = searchCites(
      nodes,
      [
        {
          text: 'Phụ lục 1',
          pageNo: 2,
          lineId: 'doc_01:s1:p002:l001',
          sourceFileId: 'doc_01',
          citation: { quote: 'Phụ lục 1', sourceFileId: 'doc_01' },
        },
      ],
      citationNumbers(nodes),
      'Điều 1 có nội dung liên quan đến Phụ lục 1.',
    )

    expect(cites).toHaveLength(1)
    expect(cites[0].id).toBe('n-2-1')
  })

  it('does not map an annex line onto a body article with the same page and line', () => {
    const nodes = buildNumberedTree([
      line(2, 5, 'Điều 2. Phạm vi công việc'),
      line(2, 6, '2.1. Nội dung thân hợp đồng.'),
    ])
    const cites = searchCites(
      nodes,
      [
        {
          text: '| 11 | Máy chủ ứng dụng cấu hình tiêu chuẩn doanh nghiệp |',
          pageNo: 2,
          lineId: 'doc_annex:s1:p002:l005',
          sourceFileId: 'doc_annex',
          citation: {
            quote: '| 11 | Máy chủ ứng dụng cấu hình tiêu chuẩn doanh nghiệp |',
            sourceFileId: 'doc_annex',
          },
        },
      ],
      citationNumbers(nodes),
      'Phụ lục 1 liệt kê | 11 | Máy chủ ứng dụng cấu hình tiêu chuẩn doanh nghiệp |',
      'doc_body',
    )

    expect(cites).toHaveLength(1)
    expect(cites[0].id).toContain('foreign:doc_annex')
    expect(cites[0].id).not.toBe('n-2-5')
  })

  it('keeps a foreign citation document and bbox for the shared highlight pane', () => {
    const nodes = buildNumberedTree([
      line(2, 1, 'Điều 1. Định nghĩa'),
    ])
    const bbox: [number, number, number, number] = [0.1, 0.2, 0.8, 0.3]
    const cites = searchCites(
      nodes,
      [
        {
          text: 'Phụ lục 1 - bảng thiết bị',
          pageNo: 1,
          lineId: 'doc_annex:s1:p001:l001',
          sourceFileId: 'doc_annex',
          bbox,
          citation: { quote: 'Phụ lục 1 - bảng thiết bị', sourceFileId: 'doc_annex', bbox },
        },
      ],
      citationNumbers(nodes),
      'Phụ lục 1 - bảng thiết bị',
      'doc_body',
    )

    expect(cites).toHaveLength(1)
    expect(cites[0].documentId).toBe('doc_annex')
    expect(cites[0].bbox).toEqual(bbox)
    expect(citationNode(cites[0]).regions).toEqual([{ pageNo: 1, bbox }])
  })

  it('recovers a table-row bbox when the citation line has no geometry', () => {
    const cite = {
      id: 'foreign:doc_annex:line-11',
      n: 91,
      quote: '| 11 | Máy chủ ứng dụng cấu hình tiêu chuẩn doanh nghiệp | bộ | 4 | 25.650.000 |',
      documentId: 'doc_annex',
      pageNo: 2,
      lineId: 'doc_annex:s1:p002:l004',
      bbox: null,
    }
    const bbox = citationTableBbox(cite, [
      {
        pageNo: 2,
        cells: [
          { row: 1, text: '11', header: false, bbox: [0.1, 0.2, 0.2, 0.22] },
          {
            row: 1,
            text: 'Máy chủ ứng dụng cấu hình tiêu chuẩn doanh nghiệp',
            header: false,
            bbox: [0.2, 0.2, 0.7, 0.22],
          },
          { row: 1, text: 'bộ', header: false, bbox: [0.7, 0.2, 0.8, 0.22] },
        ],
      },
    ])

    expect(bbox).toEqual([0.1, 0.2, 0.8, 0.22])
  })

  it('keeps citation 13, 32, and table citation 91 in the shared pane contract', () => {
    const nodes = buildNumberedTree([
      line(2, 1, 'Điều 1. Thông tin thanh toán của thân hợp đồng.'),
      line(2, 2, '1.1. Phụ lục 1 mô tả các mốc thanh toán chi tiết.'),
    ])
    const numbers = new Map(citationNumbers(nodes))
    numbers.set(nodes[0].id, 13)
    numbers.set(nodes[0].children[0].id, 32)
    numbers.set('sentinel', 90)
    const bodyQuote = nodes[0].text
    const annexQuote = nodes[0].children[0].text
    const tableQuote = '| 11 | Máy chủ ứng dụng | bộ | 4 | 25.650.000 |'
    const cites = searchCites(
      nodes,
      [
        {
          text: bodyQuote,
          pageNo: 2,
          lineId: 'doc_body:s1:p002:l001',
          sourceFileId: 'doc_body',
        },
        {
          text: annexQuote,
          pageNo: 2,
          lineId: 'doc_body:s1:p002:l002',
          sourceFileId: 'doc_body',
        },
        {
          text: tableQuote,
          pageNo: 2,
          lineId: 'doc_annex:s1:p002:l004',
          sourceFileId: 'doc_annex',
        },
      ],
      numbers,
      `${bodyQuote} ${annexQuote} ${tableQuote}`,
      'doc_body',
    )

    expect(cites.map((cite) => cite.n)).toEqual([13, 32, 91])
    expect(cites.map((cite) => cite.documentId)).toEqual([
      'doc_body',
      'doc_body',
      'doc_annex',
    ])
    expect(cites.map((cite) => citationNode(cite).nodeType)).toEqual([
      'line',
      'line',
      'line',
    ])
  })

  it('keeps both body and annex citations for a compare answer', () => {
    const nodes = buildNumberedTree([
      line(2, 1, 'HỢP ĐỒNG KINH TẾ - CUNG CẤP VÀ TRIỂN KHAI HỆ THỐNG (tiếp theo)'),
      line(2, 2, 'ĐIỀU 1. ĐỊNH NGHĨA VÀ GIẢI THÍCH'),
      line(2, 3, '1.1. "Hệ thống" là toàn bộ phần mềm, thiết bị, cấu hình, tài liệu và dịch vụ được mô tả trong hợp đồng và các phụ lục.'),
      line(2, 4, '1.2. "Ngày làm việc" là ngày không bao gồm thứ Bảy, Chủ Nhật và ngày nghỉ lễ theo quy định pháp luật Việt Nam.'),
      line(2, 5, '1.3. Trường hợp thuật ngữ có nhiều cách hiểu, ưu tiên cách hiểu phù hợp với mục tiêu, phạm vi và tài liệu đã được hai bên phê duyệt.'),
    ])
    const cites = searchCites(
      nodes,
      [
        {
          text: '|  12 | Thiết bị lưu trữ và phụ kiện mở rộng | gói | 1 | 27.000.000 | 27.000.000 | 8%  |',
          pageNo: 2,
          lineId: 'doc_annex:s1:p002:l005',
          sourceFileId: 'doc_annex',
        },
        {
          text: '1.1. "Hệ thống" là toàn bộ phần mềm, thiết bị, cấu hình, tài liệu và dịch vụ được mô tả trong hợp đồng và các phụ lục.',
          pageNo: 2,
          lineId: 'doc_body:s1:p002:l003',
          sourceFileId: 'doc_body',
        },
      ],
      citationNumbers(nodes),
      'Các đoạn liên quan trên thân HĐ và phụ lục (trích nguyên văn). Não suy ra điều nào thắng. - [Phụ lục] |  12 | Thiết bị lưu trữ và phụ kiện mở rộng | gói | 1 | 27.000.000 | 27.000.000 | 8%  | - [Thân HĐ] 1.1. "Hệ thống" là toàn bộ phần mềm, thiết bị, cấu hình, tài liệu và dịch vụ được mô tả trong hợp đồng và các phụ lục.',
      'doc_body',
    )

    expect(cites).toHaveLength(2)
    expect(cites.map((cite) => cite.id)).toEqual([
      'foreign:doc_annex:doc_annex:s1:p002:l005',
      'n-2-3',
    ])

    const answer = 'Các đoạn liên quan trên thân HĐ và phụ lục (trích nguyên văn). Không suy ra điều nào thắng / thứ tự hiệu lực.\n- [Phụ lục] |  12 | Thiết bị lưu trữ và phụ kiện mở rộng | gói | 1 | 27.000.000 | 27.000.000 | 8%  |\n- [Thân HĐ] 1.1. "Hệ thống" là toàn bộ phần mềm, thiết bị, cấu hình, tài liệu và dịch vụ được mô tả trong hợp đồng và các phụ lục.'
    const html = renderToStaticMarkup(
      <CitedAnswer
        activeId={null}
        answer={answer}
        citationOf={citationNumbers(nodes)}
        hits={[
          {
            text: '|  12 | Thiết bị lưu trữ và phụ kiện mở rộng | gói | 1 | 27.000.000 | 27.000.000 | 8%  |',
            pageNo: 2,
            lineId: 'doc_annex:s1:p002:l005',
            sourceFileId: 'doc_annex',
            bbox: null,
            citation: {
              status: 'LOCATABLE',
              sourceFileId: 'doc_annex',
              documentId: 'doc_annex',
              lineId: 'doc_annex:s1:p002:l005',
              pageNo: 2,
              bbox: null,
              nodeId: null,
              quote: '|  12 | Thiết bị lưu trữ và phụ kiện mở rộng | gói | 1 | 27.000.000 | 27.000.000 | 8%  |',
            },
          },
          {
            text: '1.1. "Hệ thống" là toàn bộ phần mềm, thiết bị, cấu hình, tài liệu và dịch vụ được mô tả trong hợp đồng và các phụ lục.',
            pageNo: 2,
            lineId: 'doc_body:s1:p002:l003',
            sourceFileId: 'doc_body',
            bbox: null,
            citation: {
              status: 'LOCATABLE',
              sourceFileId: 'doc_body',
              documentId: 'doc_body',
              lineId: 'doc_body:s1:p002:l003',
              pageNo: 2,
              bbox: null,
              nodeId: null,
              quote: '1.1. "Hệ thống" là toàn bộ phần mềm, thiết bị, cấu hình, tài liệu và dịch vụ được mô tả trong hợp đồng và các phụ lục.',
            },
          },
        ]}
        nodes={nodes}
        onCite={() => undefined}
        documentId="doc_body"
      />,
    )
    expect((html.match(/title="Trích dẫn/g) ?? []).length).toBe(2)
  })
})
