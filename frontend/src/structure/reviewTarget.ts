import type { ClauseNode, ReviewSpotSide } from '../api/structure'
import { clauseOrdinal } from '../api/clauseReview'
import { findClauseByQuote } from './citations'
import { clauseForCitation } from './conflictCite'
import type { OcrLine } from './types'

/*
 * Search lưu thẩm định theo `node.id` của cây `'numbered'` (khóa search lưu),
 * nên trang đối soát phải tra cứu bằng cùng khóa đó — không phải cây đang
 * hiển thị (`structureMode`). Cùng cách khớp trích dẫn với
 * `anchorConflicts.nodeForSide` (`conflictAnchors.ts:66-76`): ưu tiên trang +
 * dòng OCR, rồi mới thử khớp theo chữ trích dẫn. Không tự tính hash — chỉ trả
 * nút cây và số thứ tự để nơi gọi tự dựng descriptor khi cần.
 */

export type ReviewTarget = {
  node: ClauseNode
  ordinal: number
}

/**
 * Nút cây numbered khớp trích dẫn của `side`, cùng khóa tra cứu với lúc lưu.
 * Trả `null` khi không có side khớp hay trích dẫn nằm ngoài cây numbered.
 */
export function reviewTargetNode(
  numberedNodes: ClauseNode[],
  lines: OcrLine[],
  side: ReviewSpotSide,
): ReviewTarget | null {
  const node = nodeForSide(side, numberedNodes, lines)
  if (!node) return null
  return { node, ordinal: clauseOrdinal(numberedNodes, node.id) }
}

function nodeForSide(
  side: ReviewSpotSide,
  nodes: ClauseNode[],
  lines: OcrLine[],
): ClauseNode | null {
  const byLine = clauseForCitation(nodes, lines, side.pageNo, side.lineNo)
  if (byLine) return byLine
  const quote = side.quote.trim() || side.value.trim()
  if (!quote || quote === '—') return null
  return findClauseByQuote(nodes, quote, side.pageNo)
}
