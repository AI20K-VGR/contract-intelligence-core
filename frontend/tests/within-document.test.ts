import { describe, expect, it } from 'vitest'
import {
  conflictKind,
  withinDocumentId,
  withinSideLabel,
} from '../src/structure/withinDocument'

const side = (documentId: string) => ({ documentId })

describe('withinDocumentId', () => {
  it('is the document id when both sides cite the same document', () => {
    expect(withinDocumentId({ sides: [side('d1'), side('d1')] })).toBe('d1')
  })

  it('is null for a contract and annex pair', () => {
    expect(withinDocumentId({ sides: [side('d1'), side('d2')] })).toBeNull()
  })

  it('is null when a side has no document or there are fewer than two sides', () => {
    expect(withinDocumentId({ sides: [side('d1'), side('')] })).toBeNull()
    expect(withinDocumentId({ sides: [side('d1')] })).toBeNull()
    expect(withinDocumentId({ sides: [] })).toBeNull()
  })

  it('labels the sides Vế 1 and Vế 2', () => {
    expect(withinSideLabel(0)).toBe('Vế 1')
    expect(withinSideLabel(1)).toBe('Vế 2')
  })
})

describe('conflictKind', () => {
  it('is within for same-document sides, between otherwise', () => {
    expect(conflictKind({ sides: [side('d1'), side('d1')] })).toBe('within')
    expect(conflictKind({ sides: [side('d1'), side('d2')] })).toBe('between')
    expect(conflictKind({ sides: [side('d1')] })).toBe('between')
  })
})
