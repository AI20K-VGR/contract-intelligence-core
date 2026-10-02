import { describe, expect, it } from 'vitest'
import type { ClauseNode, ReviewSpot } from '../src/api/structure'
import {
  anchorConflicts,
  conflictMarkers,
  conflictSignature,
  conflictState,
  directCount,
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
    expect(markers.get('3')).toMatchObject({
      state: 'dismissed',
      below: 2,
      belowState: 'open',
    })
    expect(markers.get('3')?.spots).toHaveLength(0)
    expect(markers.get('8.1')).toMatchObject({ state: 'dismissed' })
    expect(markers.get('8')).toBeUndefined()
    expect(markers.has('9')).toBe(false)
  })

  it('uses the worst non-dismissed descendant state when the collapsed node has no direct spots', () => {
    const anchors = anchorConflicts([spot('c', 1, 4, 'confirm')], tree, lines, CONTRACT)
    const markers = conflictMarkers(anchors, tree)
    expect(markers.get('3')).toMatchObject({ below: 1, belowState: 'reviewed' })
  })

  it('excludes dismissed spots from directCount but keeps them in spots', () => {
    const anchors = anchorConflicts(
      [spot('d', 4, 1, null), spot('e', 4, 1, 'reject')],
      tree,
      lines,
      CONTRACT,
    )
    const markers = conflictMarkers(anchors, tree)
    expect(markers.get('9')?.spots).toHaveLength(2)
    expect(directCount(markers.get('9')!)).toBe(1)
  })

  it('counts a spot once when it is anchored on a node and on its own descendant', () => {
    const parentLine = line(6, 1, 0.1)
    const childLine = line(6, 2, 0.2)
    const leaf = node('leaf', 6, [childLine])
    const root = node('nestedRoot', 6, [parentLine], [leaf])
    const nested = spot('nested', 6, 1, null)
    nested.sides = [
      { ...nested.sides[0], documentId: CONTRACT, pageNo: 6, lineNo: 1 },
      { ...nested.sides[1], documentId: CONTRACT, label: 'annex', pageNo: 6, lineNo: 2 },
    ]
    const anchors = anchorConflicts([nested], [root], [parentLine, childLine], CONTRACT)
    const markers = conflictMarkers(anchors, [root])
    expect(markers.get('nestedRoot')?.spots.map((item) => item.id)).toEqual(['nested'])
    expect(markers.get('nestedRoot')?.below).toBe(0)
  })
})

describe('same-file anchors', () => {
  it('marks both pages of one document and counts the finding once on the parent', () => {
    const page3 = line(3, 7, 0.2)
    const page17 = line(17, 18, 0.4)
    const body = node('body', 3, [page3])
    const annex = node('annex', 17, [page17])
    const pair = spot('pair', 3, 7, null)
    pair.sides = [
      { ...pair.sides[0], documentId: CONTRACT, pageNo: 3, lineNo: 7 },
      {
        ...pair.sides[1],
        documentId: CONTRACT,
        label: 'annex',
        pageNo: 17,
        lineNo: 18,
      },
    ]
    const anchors = anchorConflicts([pair], [body, annex], [page3, page17], CONTRACT)
    expect([...anchors.keys()].sort()).toEqual(['annex', 'body'])
    const markers = conflictMarkers(anchors, [node('root', 1, [], [body, annex])])
    expect(markers.get('body')?.spots.map((item) => item.id)).toEqual(['pair'])
    expect(markers.get('annex')?.spots.map((item) => item.id)).toEqual(['pair'])
    expect(markers.get('root')?.below).toBe(1)
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
