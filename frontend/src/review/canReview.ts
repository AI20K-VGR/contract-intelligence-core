import type { UserRole } from '../auth/session'

/** Backend chỉ cho REVIEWER và ADMINISTRATOR lưu thẩm định (shared/acl.py, REVIEW_MUTATE). */
export function roleCanReview(role: UserRole | undefined) {
  return role === 'REVIEWER' || role === 'ADMINISTRATOR'
}
