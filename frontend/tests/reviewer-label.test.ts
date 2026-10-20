import { describe, expect, it } from 'vitest'
import { reviewerLabel } from '../src/review/reviewerLabel'

describe('reviewerLabel', () => {
  it('shows the reviewer name and email together', () => {
    expect(
      reviewerLabel({
        reviewerName: 'Admin User',
        reviewerEmail: 'admin@ci.local',
        reviewerId: 'dev-admin-keycloak-id',
      }),
    ).toBe('Admin User · admin@ci.local')
  })

  it('falls back to whichever identity field is present', () => {
    expect(
      reviewerLabel({
        reviewerName: null,
        reviewerEmail: 'admin@ci.local',
        reviewerId: 'dev-admin-keycloak-id',
      }),
    ).toBe('admin@ci.local')
    expect(
      reviewerLabel({
        reviewerName: 'Admin User',
        reviewerEmail: 'Admin User',
        reviewerId: 'dev-admin-keycloak-id',
      }),
    ).toBe('Admin User')
  })
})
