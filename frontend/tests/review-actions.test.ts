import { describe, expect, it, vi } from 'vitest'
import {
  normalizeReviewItem,
  normalizeReviewRevision,
  ReviewConflictError,
  submitReviewAction,
  type ReviewItem,
} from '../src/api/review'

describe('HITL review contract normalization', () => {
  it('normalizes a queue item with version and target snapshot', () => {
    const item = normalizeReviewItem({
      id: 'review-1',
      dossier_id: 'dos-1',
      run_id: 'run-1',
      target_type: 'party',
      target_id: 'party-a',
      reason: 'Conflicting party identity',
      priority: 'P1',
      status: 'open',
      version: 4,
      target_snapshot: { value: 'Công ty ABC' },
    })

    expect(item).toMatchObject<Partial<ReviewItem>>({
      id: 'review-1',
      dossierId: 'dos-1',
      priority: 'P1',
      version: 4,
      targetSnapshot: { value: 'Công ty ABC' },
    })
  })

  it('normalizes append-only revision data for the timeline', () => {
    const revision = normalizeReviewRevision({
      revision_number: 2,
      action: 'correct',
      author_user_id: 'reviewer-1',
      author_role: 'REVIEWER',
      comment: 'Đã đối chiếu với trang 3',
      corrected_value: { value: 'Công ty ABC' },
      previous_version: 1,
      created_at: '2026-09-25T09:00:00Z',
    })

    expect(revision).toMatchObject({
      revisionNumber: 2,
      action: 'correct',
      authorUserId: 'reviewer-1',
      previousVersion: 1,
      correctedValue: { value: 'Công ty ABC' },
    })
  })

  it('sends the optimistic-lock version and maps a 409 conflict', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: 'VERSION_CONFLICT', message: 'Version đã cũ.' },
          current_state: { version: 5, status: 'open' },
          your_submitted_action: { action: 'confirm', base_version: 4 },
        }),
        { status: 409, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      submitReviewAction('review-1', {
        action: 'confirm',
        baseVersion: 4,
      }),
    ).rejects.toMatchObject<Partial<ReviewConflictError>>({
      name: 'ReviewConflictError',
      currentState: { version: 5, status: 'open' },
    })

    const request = fetchMock.mock.calls[0]?.[1]
    expect(JSON.parse(String(request?.body))).toMatchObject({
      action: 'confirm',
      base_version: 4,
    })
    vi.unstubAllGlobals()
  })
})
