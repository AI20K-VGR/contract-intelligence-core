import { describe, expect, it } from 'vitest'
import type { ClauseNode, ReviewSpot } from '../src/api/structure'
import {
  anchorConflicts,
  conflictMarkers,
  conflictSignature,
  conflictState,
  openConflictCount,
} from '../src/structure/conflictAnchors'
import type { OcrLine } from '../src/structure/types'

const CONTRACT = 'doc-contract'
const ANNEX = 'doc-annex'

function line(pageNo: number, lineNo: number, y: number): OcrLine {
  return {
    id: `l-${pageNo}-${lineNo}`,
    pageNo,
    lineNo,
    text: `dòng ${lineNo}`,
    bbox: [0.1, y, 0.9, y + 0.02],
    pageWidth: 612,
    pageHeight: 792,
  }
}

function node(
  id: string,
  pageNo: number,
  lines: OcrLine[],
  children: ClauseNode[] = [],
): ClauseNode {
  return {
    id,
    nodeType: children.length > 0 ? 'article' : 'clause',
    label: id,
    number: id,
    title: null,
    text: `nội dung ${id}`,
    pageStart: pageNo,
    pageEnd: pageNo,
    confidence: null,
    regions: lines.map((item) => ({ pageNo: item.pageNo, bbox: item.bbox! })),
    children,
  }
}

function spot(
  id: string,
  pageNo: number,
  lineNo: number,
  latestAction: string | null,
): ReviewSpot {
  return {
    id,
    topic: `Điều ${id}`,
    rationale: '',
    severity: 'medium',
    clauseIds: [],
    sides: [
      {
        label: 'contract',
        value: '08 tuần',
        quote: '',
        documentId: CONTRACT,
        clauseId: '',
        pageNo,
        lineNo,
        regions: [],
      },
      {
        label: 'annex',
        value: '10 tuần',
        quote: '',
        documentId: ANNEX,
        clauseId: '',
        pageNo: 2,
        lineNo: 4,
        regions: [],
      },
    ],
    review: latestAction
      ? {
          itemId: `ri-${id}`,
          status: 'resolved',
          version: 2,
          latest: {
            action: latestAction,
            comment: null,
            reviewerId: 'u1',
            reviewerName: 'Admin User',
            reviewerEmail: 'admin@ci.local',
            reviewedAt: '2026-09-27T04:15:35Z',
            actionCount: 1,
          },
        }
      : null,
  }
}

const l31 = line(1, 3, 0.2)
const l32 = line(1, 4, 0.25)
const l81 = line(3, 2, 0.1)
const tree: ClauseNode[] = [
  node(
    '3',
    1,
    [line(1, 2, 0.15)],
    [node('3.1', 1, [l31]), node('3.2', 1, [l32])],
  ),
  node('8', 3, [line(3, 1, 0.05)], [node('8.1', 3, [l81])]),
  node('9', 4, [line(4, 1, 0.05)]),
]
const lines = [
  line(1, 2, 0.15),
  l31,
  l32,
  line(3, 1, 0.05),
  l81,
  line(4, 1, 0.05),
]

describe('conflictState', () => {
  it('is open without a review, dismissed on reject, reviewed otherwise', () => {
    expect(conflictState(spot('a', 1, 3, null))).toBe('open')
    expect(conflictState(spot('a', 1, 3, 'reject'))).toBe('dismissed')
    expect(conflictState(spot('a', 1, 3, 'confirm'))).toBe('reviewed')
    expect(conflictState(spot('a', 1, 3, 'correct'))).toBe('reviewed')
  })
})

describe('anchorConflicts', () => {
  it('maps each conflict to the tree node that owns the contract-side OCR line', () => {
    const anchors = anchorConflicts(
      [spot('a', 1, 3, null), spot('b', 3, 2, 'reject')],
      tree,
      lines,
      CONTRACT,
    )
    expect([...anchors.keys()].sort()).toEqual(['3.1', '8.1'])
    expect(anchors.get('3.1')?.map((item) => item.id)).toEqual(['a'])
  })

  it('ignores conflicts whose contract-side line is not in the tree', () => {
    const anchors = anchorConflicts(
      [spot('x', 9, 9, null)],
      tree,
      lines,
      CONTRACT,
    )
    expect(anchors.size).toBe(0)
  })
})

describe('conflictMarkers', () => {
  it('marks the node, rolls live counts up to ancestors and skips dismissed ones', () => {
    const anchors = anchorConflicts(
      [
        spot('a', 1, 3, null),
        spot('c', 1, 4, 'confirm'),
        spot('b', 3, 2, 'reject'),
      ],
      tree,
      lines,
      CONTRACT,
    )
    const markers = conflictMarkers(anchors, tree)
    expect(markers.get('3.1')).toMatchObject({ state: 'open', below: 0 })
    expect(markers.get('3.2')).toMatchObject({ state: 'reviewed', below: 0 })
    expect(markers.get('3')).toMatchObject({ state: 'dismissed', below: 2 })
    expect(markers.get('3')?.spots).toHaveLength(0)
    expect(markers.get('8.1')).toMatchObject({ state: 'dismissed' })
    expect(markers.get('8')).toBeUndefined()
    expect(markers.has('9')).toBe(false)
  })
})

describe('conflict summary helpers', () => {
  it('counts only unreviewed conflicts and changes the signature on new reviews', () => {
    const before = [spot('a', 1, 3, null), spot('b', 3, 2, 'reject')]
    expect(openConflictCount(before)).toBe(1)
    const after = [spot('a', 1, 3, 'confirm'), before[1]]
    expect(conflictSignature(before)).not.toBe(conflictSignature(after))
  })
})

describe('anchorConflicts within one contract', () => {
  it('marks both clauses when both sides cite the same document', () => {
    const inside = spot('w', 1, 3, null)
    inside.sides[1] = {
      ...inside.sides[1],
      label: 'contract',
      documentId: CONTRACT,
      pageNo: 3,
      lineNo: 2,
    }
    const anchors = anchorConflicts([inside], tree, lines, CONTRACT)
    expect([...anchors.keys()].sort()).toEqual(['3.1', '8.1'])
    expect(anchors.get('3.1')?.[0].id).toBe('w')
    expect(anchors.get('8.1')?.[0].id).toBe('w')
  })
})
