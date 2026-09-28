import { describe, expect, it } from 'vitest'
import type { OcrLine } from '../src/structure/types'
import { boxesForQuote } from '../src/structure/quoteBoxes'

function line(
  pageNo: number,
  text: string,
  bbox: [number, number, number, number],
): OcrLine {
  return {
    id: `${pageNo}-${text}`,
    pageNo,
    lineNo: 1,
    text,
    bbox,
    pageWidth: 612,
    pageHeight: 792,
  }
}

describe('boxesForQuote', () => {
  it('khoanh các dòng thuộc câu trích trên đúng trang', () => {
    const lines = [
      line(2, 'Điều khoản khác không liên quan đến phạt', [0.1, 0.1, 0.8, 0.14]),
      line(14, 'Mức phạt vi phạm nghĩa vụ thanh toán là', [0.1, 0.4, 0.8, 0.44]),
      line(14, '0,12%/ngày tính trên số tiền chậm trả.', [0.1, 0.45, 0.7, 0.49]),
    ]
    const boxes = boxesForQuote(
      lines,
      'Mức phạt vi phạm nghĩa vụ thanh toán là 0,12%/ngày tính trên số tiền chậm trả.',
      14,
    )
    expect(boxes).toHaveLength(2)
    expect(boxes.every((box) => box.pageNo === 14)).toBe(true)
  })

  it('bỏ qua câu quá ngắn và dòng không có bbox', () => {
    const lines = [
      line(1, 'Một câu dài đủ để khớp với trích dẫn', [0, 0, 1, 0.1]),
    ]
    lines[0] = { ...lines[0], bbox: null }
    expect(boxesForQuote(lines, 'Một câu dài đủ để khớp với trích dẫn', 1)).toEqual(
      [],
    )
    expect(boxesForQuote(lines, 'ngắn', null)).toEqual([])
  })
})
