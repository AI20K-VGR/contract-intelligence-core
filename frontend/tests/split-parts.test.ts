import { describe, expect, it } from 'vitest'
import {
  addPart,
  initialParts,
  removePart,
  resolveParts,
  toRequestParts,
  validateParts,
} from '../src/split/parts'

describe('split parts', () => {
  it('starts as one contract covering the whole file', () => {
    const parts = initialParts(10)
    expect(toRequestParts(parts, 10)).toEqual([
      { page_start: 1, page_end: 10, role: 'contract' },
    ])
    expect(validateParts(parts, 10)).toBeNull()
  })

  it('adding a part splits the last one and always covers 1..N', () => {
    const parts = addPart(initialParts(10), 10)
    const resolved = resolveParts(parts, 10)
    expect(resolved).toHaveLength(2)
    expect(resolved[0].pageStart).toBe(1)
    expect(resolved[1].pageStart).toBe(resolved[0].pageEnd + 1)
    expect(resolved[1].pageEnd).toBe(10)
    expect(resolved[1].role).toBe('annex')
    expect(validateParts(parts, 10)).toBeNull()
  })

  it('does not add a part when the last one has a single page', () => {
    const one = initialParts(1)
    expect(addPart(one, 1)).toBe(one)
  })

  it('requires exactly one contract', () => {
    const parts = addPart(initialParts(10), 10)
    expect(
      validateParts(
        parts.map((part) => ({ ...part, role: 'annex' as const })),
        10,
      ),
    ).toMatch(/chưa có/)
    expect(
      validateParts(
        parts.map((part) => ({ ...part, role: 'contract' as const })),
        10,
      ),
    ).toMatch(/hiện có 2/)
  })

  it('rejects a part that ends before it starts', () => {
    const parts = addPart(addPart(initialParts(10), 10), 10)
    const broken = parts.map((part, index) =>
      index === 1 ? { ...part, end: 0 } : part,
    )
    expect(validateParts(broken, 10)).not.toBeNull()
  })

  it('removing a part gives its pages to the next one, keeping 1..N', () => {
    const parts = addPart(initialParts(10), 10)
    const kept = removePart(parts, parts[0].key)
    expect(toRequestParts(kept, 10)).toEqual([
      { page_start: 1, page_end: 10, role: 'annex' },
    ])
  })

  it('refuses unknown page count', () => {
    expect(validateParts(initialParts(0), 0)).not.toBeNull()
  })
})
