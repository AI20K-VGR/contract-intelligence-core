import { describe, expect, it } from 'vitest'
import { isOcrComplete, isRunFinished } from '../src/api/structure'

describe('isRunFinished', () => {
  it('does not treat extracted as finished: AI2 still runs after OCR', () => {
    expect(isOcrComplete('extracted')).toBe(true)
    expect(isRunFinished('extracted')).toBe(false)
  })

  it('finishes once the dossier reaches review', () => {
    expect(isRunFinished('pending_review')).toBe(true)
    expect(isRunFinished('reviewed')).toBe(true)
    expect(isRunFinished('approved')).toBe(true)
  })

  it('is false for running, stopped and missing statuses', () => {
    expect(isRunFinished('processing')).toBe(false)
    expect(isRunFinished('failed')).toBe(false)
    expect(isRunFinished(null)).toBe(false)
    expect(isRunFinished(undefined)).toBe(false)
  })
})

describe('shared dossier status meaning', () => {
  it('treats every finished status as OCR-complete too', () => {
    for (const status of ['pending_review', 'reviewed', 'approved']) {
      expect(isOcrComplete(status)).toBe(true)
      expect(isRunFinished(status)).toBe(true)
    }
  })
})
