import type { ClauseNode, ReviewSpot, ReviewSpotSide } from '../api/structure'
import { findClauseByQuote } from './citations'
import { clauseForCitation } from './conflictCite'
import type { OcrLine } from './types'

/*
 * Cây cấu trúc dựng theo hợp đồng. Xung đột do máy phát hiện neo bằng
 * trang + dòng OCR của trích dẫn bên hợp đồng, nên phải đổi sang nút cây
 * đang chứa dòng đó rồi mới tô được màu. Trạng thái lấy từ lượt thẩm định
 * xung đột gần nhất; cây không tự kết luận bên nào có hiệu lực.
 */

export type ConflictState = 'open' | 'reviewed' | 'dismissed'

export const CONFLICT_STATE_LABEL: Record<ConflictState, string> = {
  open: 'Có xung đột, chưa ai thẩm định',
  reviewed: 'Xung đột đã được thẩm định',
  dismissed: 'Máy báo xung đột, đã thẩm định là sai lệch',
}

export const VERDICT_LABEL: Record<string, string> = {
  confirm: 'Đúng',
  reject: 'Sai',
  correct: 'Đúng (có bổ sung)',
}

/** Trạng thái một xung đột theo lượt thẩm định gần nhất. */
export function conflictState(spot: ReviewSpot): ConflictState {
  const action = spot.review?.latest?.action
  if (!action) return 'open'
  return action === 'reject' ? 'dismissed' : 'reviewed'
}

const STATE_RANK: Record<ConflictState, number> = {
  open: 0,
  reviewed: 1,
  dismissed: 2,
}

/** Trạng thái nặng nhất trong một nhóm xung đột. */
export function worstState(spots: ReviewSpot[]): ConflictState {
  let worst: ConflictState = 'dismissed'
  for (const spot of spots) {
    const state = conflictState(spot)
    if (STATE_RANK[state] < STATE_RANK[worst]) worst = state
  }
  return spots.length > 0 ? worst : 'dismissed'
}

export type ConflictMarker = {
  /** Xung đột neo trực tiếp vào nút này. */
  spots: ReviewSpot[]
  /** Trạng thái nặng nhất của các xung đột trực tiếp. */
  state: ConflictState
  /** Số xung đột còn hiệu lực (chưa bị đánh Sai) nằm trong nhánh con. */
  below: number
}

function sidesOn(spot: ReviewSpot, documentId: string | null) {
  const own = documentId
    ? spot.sides.filter((side) => side.documentId === documentId)
    : []
  return own.length > 0 ? own : documentId ? [] : spot.sides.slice(0, 1)
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

/**
 * id nút cây → các xung đột có trích dẫn nằm trong nút đó (trên tài liệu
 * đang xem). Một xung đột chỉ neo một lần vào một nút.
 */
export function anchorConflicts(
  spots: ReviewSpot[],
  nodes: ClauseNode[],
  lines: OcrLine[],
  documentId: string | null,
): Map<string, ReviewSpot[]> {
  const anchors = new Map<string, ReviewSpot[]>()
  if (nodes.length === 0) return anchors
  for (const spot of spots) {
    // Mỗi vế nằm trên tài liệu này đều được đánh dấu. Xung đột trong một hợp
    // đồng có hai vế cùng file nên hiện ở cả hai điều khoản.
    for (const side of sidesOn(spot, documentId)) {
      const target = nodeForSide(side, nodes, lines)
      if (!target) continue
      const list = anchors.get(target.id)
      if (list) {
        if (!list.some((item) => item.id === spot.id)) list.push(spot)
      } else {
        anchors.set(target.id, [spot])
      }
    }
  }
  return anchors
}

/**
 * Đánh dấu cho từng nút: nút có xung đột trực tiếp và mọi cấp cha của nó
 * (cha đang gấp vẫn hiện số xung đột bên trong).
 */
export function conflictMarkers(
  anchors: ReadonlyMap<string, ReviewSpot[]>,
  nodes: ClauseNode[],
): Map<string, ConflictMarker> {
  const markers = new Map<string, ConflictMarker>()
  if (anchors.size === 0) return markers

  function visit(node: ClauseNode): number {
    let below = 0
    for (const child of node.children) below += visit(child)
    const spots = anchors.get(node.id) ?? []
    const live = spots.filter((spot) => conflictState(spot) !== 'dismissed').length
    if (spots.length > 0 || below > 0) {
      markers.set(node.id, { spots, state: worstState(spots), below })
    }
    return below + live
  }
  for (const node of nodes) visit(node)
  return markers
}

/** Số xung đột còn hiệu lực trong cả hồ sơ, để hiện cạnh nút "Xem xung đột". */
export function openConflictCount(spots: ReviewSpot[]) {
  return spots.filter((spot) => conflictState(spot) === 'open').length
}

/** Chữ ký để nhớ người dùng đã tắt banner: đổi khi có thẩm định mới hoặc chạy lại. */
export function conflictSignature(spots: ReviewSpot[]) {
  return spots
    .map((spot) => `${spot.id}@${spot.review?.version ?? 0}`)
    .sort()
    .join('|')
}
