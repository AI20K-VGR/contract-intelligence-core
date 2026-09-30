import { describe, expect, it } from 'vitest'
import { mergeTimelines, timelineEntries } from '../src/review/timeline'

const who = {
  reviewerId: 'dev-admin-keycloak-id',
  reviewerName: 'Admin User',
  reviewerEmail: 'admin@ci.local',
}

describe('review timeline', () => {
  it('keeps citation and conflict reviews apart but on one clock, newest first', () => {
    const conflict = timelineEntries('finding', '', 'finding:f1', [
      {
        revisionNumber: 1,
        action: 'correct',
        comment: 'trang thấy k đúng',
        assessment: 'trang thấy k đúng',
        createdAt: '2026-09-27T04:15:18Z',
        ...who,
      },
      {
        revisionNumber: 2,
        action: 'reject',
        comment: 'đúng channie thấy sai',
        assessment: null,
        createdAt: '2026-09-27T04:15:35Z',
        ...who,
      },
    ])
    const citation = timelineEntries('citation', 'Hợp đồng', 'clause:n-5-8', [
      {
        revisionNumber: 1,
        action: 'confirm',
        comment: 'trang nói chính xác',
        assessment: null,
        createdAt: '2026-09-27T04:15:25Z',
        ...who,
      },
    ])

    const merged = mergeTimelines(conflict, citation)
    expect(merged.map((entry) => `${entry.kind}:${entry.action}`)).toEqual([
      'finding:reject',
      'citation:confirm',
      'finding:correct',
    ])
    expect(merged[1]).toMatchObject({
      source: 'Hợp đồng',
      who: 'Admin User · admin@ci.local',
      note: 'trang nói chính xác',
    })
    expect(merged[2].note).toBe('trang thấy k đúng')
  })
})
