import { describe, expect, it } from 'vitest'
import { roleCanReview } from '../src/review/canReview'

describe('roleCanReview', () => {
  it('lets reviewers and admins review, not operators', () => {
    expect(roleCanReview('REVIEWER')).toBe(true)
    expect(roleCanReview('ADMINISTRATOR')).toBe(true)
    expect(roleCanReview('OPERATOR')).toBe(false)
    expect(roleCanReview(undefined)).toBe(false)
  })
})
