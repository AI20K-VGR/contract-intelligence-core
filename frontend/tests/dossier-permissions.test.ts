import { describe, expect, it, vi } from 'vitest'

vi.mock('../src/api/structure', () => ({ getDossierStructure: vi.fn() }))
vi.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ user: null }) }))

const { dossierPermissions } = await import('../src/auth/dossierPermissions')

const now = new Date('2026-10-12T00:00:00Z').getTime()
const operator = {
  id: 'op',
  email: 'op@ci.local',
  backendRole: 'OPERATOR' as const,
}
const reviewer = {
  id: 'rv',
  email: 'rv@ci.local',
  backendRole: 'REVIEWER' as const,
}
const admin = {
  id: 'ad',
  email: 'ad@ci.local',
  backendRole: 'ADMINISTRATOR' as const,
}

function sharedWith(grant: Record<string, unknown>) {
  return { created_by: 'someone', shared_with: [grant] }
}

describe('dossierPermissions (mirrors shared/acl.py)', () => {
  it('owner operator edits and manages, but never reviews', () => {
    const p = dossierPermissions(operator, { created_by: 'op' }, now)
    expect(p.canEdit).toBe(true)
    expect(p.canManage).toBe(true)
    expect(p.canReview).toBe(false)
    expect(p.canSeeReview).toBe(false)
    expect(p.reviewBlocked).toContain('Thẩm định')
  })

  it('operator with a read grant only views', () => {
    const p = dossierPermissions(
      operator,
      sharedWith({ id: 'op', permission: 'read' }),
      now,
    )
    expect(p.grant).toBe('read')
    expect(p.canEdit).toBe(false)
    expect(p.canManage).toBe(false)
    expect(p.editBlocked).toContain('chỉ có quyền xem')
  })

  it('reviewer with an edit grant reviews but does not edit or approve', () => {
    const p = dossierPermissions(
      reviewer,
      sharedWith({ email: 'RV@ci.local', permission: 'edit' }),
      now,
    )
    expect(p.canReview).toBe(true)
    expect(p.canSeeReview).toBe(true)
    expect(p.canEdit).toBe(false)
    expect(p.canApprove).toBe(false)
  })

  it('reviewer with a read grant sees the queue but cannot review', () => {
    const p = dossierPermissions(
      reviewer,
      sharedWith({ id: 'rv', permission: 'read' }),
      now,
    )
    expect(p.canSeeReview).toBe(true)
    expect(p.canReview).toBe(false)
    expect(p.reviewBlocked).toContain('chỉ có quyền xem')
  })

  it('a grant without permission is a legacy edit grant', () => {
    expect(
      dossierPermissions(reviewer, sharedWith({ id: 'rv' }), now).canReview,
    ).toBe(true)
  })

  it('expired or disabled grants give nothing', () => {
    const expired = dossierPermissions(
      reviewer,
      sharedWith({ id: 'rv', expires_at: '2026-10-01T00:00:00Z' }),
      now,
    )
    expect(expired.expired).toBe(true)
    expect(expired.canSeeReview).toBe(false)
    expect(expired.reviewBlocked).toContain('hết hạn')
    const disabled = dossierPermissions(
      reviewer,
      sharedWith({ id: 'rv', status: 'disabled' }),
      now,
    )
    expect(disabled.canSeeReview).toBe(false)
  })

  it('access_scope "mine" ignores leftover grants', () => {
    const p = dossierPermissions(
      reviewer,
      { created_by: 'x', access_scope: 'mine', shared_with: [{ id: 'rv' }] },
      now,
    )
    expect(p.canSeeReview).toBe(false)
  })

  it('admin manages any dossier but approves only with an edit grant', () => {
    expect(dossierPermissions(admin, { created_by: 'x' }, now).canManage).toBe(
      true,
    )
    expect(dossierPermissions(admin, { created_by: 'x' }, now).canApprove).toBe(
      false,
    )
    expect(
      dossierPermissions(admin, sharedWith({ id: 'ad' }), now).canApprove,
    ).toBe(true)
  })

  it('falls back to the role before the dossier is loaded', () => {
    const p = dossierPermissions(operator, undefined, now)
    expect(p.known).toBe(false)
    expect(p.canEdit).toBe(true)
    expect(p.canReview).toBe(false)
  })
})
