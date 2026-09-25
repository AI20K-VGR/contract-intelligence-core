import { describe, expect, it } from 'vitest'
import { inferStructureMode } from '../src/structure'
import type { OcrLine } from '../src/structure/types'

function line(text: string): OcrLine {
  return {
    id: text,
    pageNo: 1,
    lineNo: 1,
    text,
    bbox: null,
    pageWidth: 0,
    pageHeight: 0,
  }
}

describe('inferStructureMode', () => {
  it('selects tables when OCR has no numbered headings but tables exist', () => {
    expect(inferStructureMode([line('| STT | Nội dung |')], true)).toBe(
      'tables',
    )
  })

  it('keeps numbered contracts on the numbered structure view', () => {
    expect(inferStructureMode([line('1. Phạm vi công việc')], true)).toBe(
      'numbered',
    )
  })
})
