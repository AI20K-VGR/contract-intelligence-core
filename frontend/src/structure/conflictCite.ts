import type { ClauseNode, ClauseRegion } from '../api/structure'
import type { OcrLine } from './types'

function closeBox(
  left: [number, number, number, number],
  right: [number, number, number, number],
) {
  return left.every((value, index) => Math.abs(value - right[index]) < 0.01)
}

/**
 * Nút cây cấu trúc đang chứa đúng dòng OCR của trích dẫn.
 * Cùng cách khoanh với việc bấm nút đó trên cây: lấy mọi region của nút.
 */
export function clauseForCitation(
  nodes: ClauseNode[],
  lines: OcrLine[],
  pageNo: number | null,
  lineNo: number | null,
): ClauseNode | null {
  if (!pageNo || !lineNo) return null
  const line = lines.find(
    (item) => item.pageNo === pageNo && item.lineNo === lineNo && item.bbox,
  )
  if (!line?.bbox) return null
  return ownerOf(nodes, pageNo, line.bbox)
}

function ownerOf(
  nodes: ClauseNode[],
  pageNo: number,
  bbox: [number, number, number, number],
): ClauseNode | null {
  for (const node of nodes) {
    const child = ownerOf(node.children, pageNo, bbox)
    if (child) return child
    const owns = node.regions.some(
      (region) => region.pageNo === pageNo && closeBox(region.bbox, bbox),
    )
    if (owns) return node
  }
  return null
}

export function regionsOf(node: ClauseNode | null): ClauseRegion[] {
  if (!node) return []
  return node.regions.filter((region) => {
    const [x0, y0, x1, y1] = region.bbox
    const area = Math.max(0, x1 - x0) * Math.max(0, y1 - y0)
    return area > 0.0001 && area <= 1
  })
}
