import { describe, expect, it } from 'vitest'
import {
  asConfidence,
  confidenceLevel,
  formatConfidence,
  needsReview,
  weakestConfidence,
} from '../src/structure/confidence'

describe('confidence levels', () => {
  it('maps scores onto the review thresholds', () => {
    expect(confidenceLevel(0.97)).toBe('high')
    expect(confidenceLevel(0.95)).toBe('high')
    expect(confidenceLevel(0.9)).toBe('medium')
    expect(confidenceLevel(0.3)).toBe('low')
    expect(needsReview(0.84)).toBe(true)
    expect(needsReview(0.85)).toBe(false)
    expect(needsReview(null)).toBe(false)
  })

  it('never rounds a score up', () => {
    expect(formatConfidence(0.29)).toBe('29%')
    expect(formatConfidence(0.949)).toBe('94%')
    expect(formatConfidence(0.97)).toBe('97%')
  })

  it('treats missing or out-of-range values as unknown', () => {
    expect(asConfidence(undefined)).toBeNull()
    expect(asConfidence(1.2)).toBeNull()
    expect(asConfidence(0.9)).toBe(0.9)
    expect(weakestConfidence([0.97, null, 0.5])).toBe(0.5)
    expect(weakestConfidence([null])).toBeNull()
  })
})
