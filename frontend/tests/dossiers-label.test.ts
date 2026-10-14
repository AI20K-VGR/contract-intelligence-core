import { describe, expect, it } from 'vitest'
import { dossiersLabel } from '../src/auth/session'

describe('dossiersLabel', () => {
  it('names the dossier list by what each role does with it', () => {
    expect(dossiersLabel('admin', 'ADMINISTRATOR')).toBe('Hồ sơ')
    expect(dossiersLabel('user', 'OPERATOR')).toBe('Hồ sơ của tôi')
    expect(dossiersLabel('user', 'REVIEWER')).toBe('Hồ sơ được giao')
    expect(dossiersLabel('user')).toBe('Hồ sơ của tôi')
  })
})
