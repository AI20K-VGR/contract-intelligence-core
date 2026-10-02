import { describe, expect, it } from 'vitest'
import { clauseOrdinal } from '../src/api/clauseReview'
import { reviewTargetNode } from '../src/structure/reviewTarget'
import type { ClauseNode, ReviewSpotSide } from '../src/api/structure'
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
    nodeType: 'clause',
    label: 'Điều 1',
    number: '1',
    title: 'Đối tượng hợp đồng',
    text: 'Điều 1. Đối tượng hợp đồng',
    pageStart: 3,
    pageEnd: 3,
    confidence: null,
    regions,
    children,
  }
}

function side(overrides: Partial<ReviewSpotSide> = {}): ReviewSpotSide {
  return {
    label: 'Hợp đồng',
    value: 'Điều 1. Đối tượng hợp đồng',
    quote: 'Điều 1. Đối tượng hợp đồng',
    documentId: 'doc-1',
    clauseId: 'clause-numbered',
    pageNo: 3,
    lineNo: 1,
    regions: [],
    ...overrides,
  }
}

const BBOX: [number, number, number, number] = [0.1, 0.1, 0.9, 0.2]
const LINES = [line(3, 1, 'Điều 1. Đối tượng hợp đồng', BBOX)]

describe('reviewTargetNode', () => {
  it('lấy nút từ cây numbered, không phải cây đang xem (structureMode khác)', () => {
    const numberedNodes = [node('clause-numbered', [{ pageNo: 3, bbox: BBOX }])]
    // Cây structureMode (freeform) khác, cùng dòng nhưng id khác — không được
    // truyền vào reviewTargetNode, chỉ dựng để chứng minh hai cây thật sự lệch id.
    const freeformNodes = [node('clause-freeform', [{ pageNo: 3, bbox: BBOX }])]
    expect(freeformNodes[0].id).not.toBe(numberedNodes[0].id)

    const result = reviewTargetNode(numberedNodes, LINES, side())

    expect(result?.node.id).toBe('clause-numbered')
  })

  it('ordinal tính trên cây numbered để descriptor khớp lượt thẩm định đã lưu', () => {
    const numberedNodes = [
      node('clause-other', [{ pageNo: 5, bbox: [0.2, 0.2, 0.8, 0.3] }]),
      node('clause-numbered', [{ pageNo: 3, bbox: BBOX }]),
    ]

    const result = reviewTargetNode(numberedNodes, LINES, side())

    expect(result?.ordinal).toBe(clauseOrdinal(numberedNodes, 'clause-numbered'))
  })

  it('trả null khi trích dẫn không khớp nút nào trên cây numbered', () => {
    const numberedNodes = [node('clause-numbered', [{ pageNo: 3, bbox: BBOX }])]
    const missing = side({
      pageNo: 99,
      lineNo: 99,
      quote: 'Câu không tồn tại trong hồ sơ này',
      value: 'Câu không tồn tại trong hồ sơ này',
    })

    expect(reviewTargetNode(numberedNodes, LINES, missing)).toBeNull()
  })
})
