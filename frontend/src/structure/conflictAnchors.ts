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
  confirm: 'Chính xác',
  reject: 'Sai lệch',
  correct: 'Sửa nhận định',
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
  /** Số xung đột còn hiệu lực (chưa bị đánh Sai lệch) nằm trong nhánh con. */
  below: number
  /** Trạng thái nặng nhất trong các xung đột thuộc nhánh con (không tính trực tiếp). */
  belowState: ConflictState
}

/** Số xung đột trực tiếp còn hiệu lực (loại các xung đột đã đánh Sai lệch). */
export function directCount(marker: ConflictMarker): number {
  return marker.spots.filter((spot) => conflictState(spot) !== 'dismissed').length
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
    const targets: ClauseNode[] = []
    for (const side of sidesOn(spot, documentId)) {
      const target = nodeForSide(side, nodes, lines)
      if (target && !targets.some((item) => item.id === target.id)) {
        targets.push(target)
      }
    }
    for (const target of targets) {
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

  function visit(node: ClauseNode): Map<string, ConflictState> {
    const descendant = new Map<string, ConflictState>()
    for (const child of node.children) {
      for (const [id, state] of visit(child)) descendant.set(id, state)
    }
    const spots = anchors.get(node.id) ?? []
    // Một xung đột neo cả vào nút này lẫn vào một hậu duệ chỉ đếm 1 lần —
    // bỏ id trực tiếp khỏi tập hậu duệ trước khi ghi `below`.
    for (const spot of spots) descendant.delete(spot.id)
    if (spots.length > 0 || descendant.size > 0) {
      let belowState: ConflictState = 'dismissed'
      for (const state of descendant.values()) {
        if (STATE_RANK[state] < STATE_RANK[belowState]) belowState = state
      }
      markers.set(node.id, {
        spots,
        state: worstState(spots),
        below: descendant.size,
        belowState,
      })
    }
    for (const spot of spots) {
      if (conflictState(spot) !== 'dismissed') descendant.set(spot.id, conflictState(spot))
    }
    return descendant
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
