import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import {
  FindingQueue,
  type FindingQueueEntry,
} from '../src/components/FindingQueue'

const entry: FindingQueueEntry = {
  item: {
    id: 'review-finding-1',
    dossierId: 'dossier-real-1',
    runId: 'run-1',
    targetType: 'finding',
    targetId: 'finding-1',
    reason: 'Hai phía evidence lệch nhau',
    priority: 'P1',
    status: 'open',
    version: 4,
    sourceTraceId: 'trace-1',
    sourceObservationId: null,
    targetSnapshot: { severity: 'HIGH', topic: 'Thời hạn SLA' },
    createdAt: '2026-09-25T09:00:00Z',
  },
  severity: 'HIGH',
  topic: 'Thời hạn SLA',
  leftEvidence: 'Body: 30 ngày',
  rightEvidence: 'Annex: 15 ngày',
  revisions: [
    {
      revisionNumber: 3,
      action: 'correct',
      authorUserId: 'reviewer-1',
      authorRole: 'REVIEWER',
      comment: 'Đã đối chiếu lại annex.',
      correctedValue: null,
      correctedBbox: null,
      previousVersion: 3,
      createdAt: '2026-09-25T09:01:00Z',
    },
  ],
}

describe('FindingQueue', () => {
  it('renders severity, two-sided evidence, base version and revision audit', () => {
    const html = renderToStaticMarkup(
      <FindingQueue
        entries={[entry]}
        onAction={() => undefined}
        onReload={() => undefined}
      />,
    )

    expect(html).toContain('HIGH')
    expect(html).toContain('Body: 30 ngày')
    expect(html).toContain('Annex: 15 ngày')
    expect(html).toContain('base_version: 4')
    expect(html).toContain('Đã đối chiếu lại annex.')
    expect(html).toContain('Xác nhận')
    expect(html).toContain('Từ chối')
  })
})
