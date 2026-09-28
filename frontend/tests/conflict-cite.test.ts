import { describe, expect, it } from 'vitest'
import { clauseForCitation, sameFileCitationSides } from '../src/structure/conflictCite'
import type { ClauseNode } from '../src/api/structure'
import type { OcrLine } from '../src/structure/types'

function line(
  pageNo: number,
  lineNo: number,
  text: string,
  bbox: [number, number, number, number],
): OcrLine {
  return {
    id: `${pageNo}-${lineNo}`,
    pageNo,
    lineNo,
    text,
    bbox,
    pageWidth: 612,
    pageHeight: 792,
  }
}

function node(
  id: string,
  regions: ClauseNode['regions'],
  children: ClauseNode[] = [],
): ClauseNode {
  return {
    id,
    nodeType: 'annex',
    label: 'Phụ lục 01',
    number: '01',
    title: 'Bảng khối lượng',
    text: 'PHỤ LỤC 01 - BẢNG KHỐI LƯỢNG',
    pageStart: 15,
    pageEnd: 15,
    confidence: null,
    regions,
    children,
  }
}

describe('clauseForCitation', () => {
  it('trả đúng nút cây đang chứa dòng trích, giống khi bấm trên cây', () => {
    const bbox: [number, number, number, number] = [0.24, 0.03, 0.76, 0.05]
    const annex = node('annex-01', [{ pageNo: 15, bbox }])
    const other = node('other', [{ pageNo: 10, bbox: [0.1, 0.1, 0.2, 0.2] }])
    const found = clauseForCitation(
      [other, annex],
      [line(15, 1, 'PHỤ LỤC 01 - BẢNG KHỐI LƯỢNG', bbox)],
      15,
      1,
    )
    expect(found?.id).toBe('annex-01')
  })

  it('bỏ qua khi không có dòng OCR khớp', () => {
    expect(clauseForCitation([], [], 15, 1)).toBeNull()
  })
})

describe('sameFileCitationSides', () => {
  it('giữ hai trích dẫn khi thân và phụ lục nằm trong cùng một file', () => {
    const sides = sameFileCitationSides([
      {
        documentId: 'doc-1',
        label: 'Thân',
        quote: '1.286.400.000 đồng',
        pageNo: 3,
      },
      {
        documentId: 'doc-1',
        label: 'Phụ lục 01',
        quote: '4.149.360.000',
        pageNo: 17,
      },
    ])
    expect(sides?.map((side) => side.pageNo)).toEqual([3, 17])
  })

  it('để trang ghép theo tài liệu khi hai phía thuộc hai file', () => {
    expect(
      sameFileCitationSides([
        { documentId: 'doc-a', label: 'Hợp đồng', quote: 'A', pageNo: 1 },
        { documentId: 'doc-b', label: 'Phụ lục', quote: 'B', pageNo: 2 },
      ]),
    ).toBeNull()
  })
})
