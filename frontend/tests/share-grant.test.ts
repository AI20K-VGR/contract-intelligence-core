import { describe, expect, it } from 'vitest'
import {
  fromDateInput,
  grantPermission,
  isGrantExpired,
  toDateInput,
} from '../src/data/shareGrant'

describe('share grant helpers', () => {
  it('treats a grant without permission as edit (legacy shares)', () => {
    expect(grantPermission({})).toBe('edit')
    expect(grantPermission({ permission: 'read' })).toBe('read')
  })

  it('never expires without a date, expires at or past the date', () => {
    const now = new Date('2026-10-01T12:00:00Z').getTime()
    expect(isGrantExpired({ expires_at: null }, now)).toBe(false)
    expect(isGrantExpired({}, now)).toBe(false)
    expect(isGrantExpired({ expires_at: '2026-10-02T00:00:00Z' }, now)).toBe(
      false,
    )
    expect(isGrantExpired({ expires_at: '2026-10-01T12:00:00Z' }, now)).toBe(
      true,
    )
    expect(isGrantExpired({ expires_at: 'không phải ngày' }, now)).toBe(true)
  })

  it('round-trips the date picker value as end of that local day', () => {
    expect(fromDateInput('')).toBeNull()
    const iso = fromDateInput('2026-10-05')
    expect(toDateInput(iso)).toBe('2026-10-05')
    expect(new Date(iso as string).getHours()).toBe(23)
  })
})
