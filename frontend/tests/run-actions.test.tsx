import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { normalizeAi2SearchResult } from '../src/api/ai2'
import { isReOcrFinished } from '../src/api/reocr'
import { isCancellableRun, runStatusLabel } from '../src/api/runs'
import { SearchAudit } from '../src/components/SearchAudit'

describe('run helpers', () => {
  it('only lets queued or running runs be cancelled', () => {
    expect(isCancellableRun('running')).toBe(true)
    expect(isCancellableRun('queued')).toBe(true)
    expect(isCancellableRun('completed')).toBe(false)
    expect(isCancellableRun('cancelled')).toBe(false)
  })

  it('labels run statuses in Vietnamese', () => {
    expect(runStatusLabel('completed')).toBe('Hoàn thành')
    expect(runStatusLabel('failed')).toBe('Lỗi')
    expect(runStatusLabel('')).toBe('Chưa rõ')
  })
})

describe('re-OCR request status', () => {
  it('treats terminal statuses as finished', () => {
    expect(isReOcrFinished('completed')).toBe(true)
    expect(isReOcrFinished('FAILED')).toBe(true)
    expect(isReOcrFinished('running')).toBe(false)
  })
})

describe('search audit', () => {
  const base = { hits: [], answer: 'x', retrieval_layer: { mode: 'hybrid' } }

  it('warns when AI2 filtered citations by permission', () => {
    const result = normalizeAi2SearchResult(
      { ...base, acl_decision: 'filtered', trace_id: 'qtr_1' },
      'dos_1',
    )
    expect(result.aclDecision).toBe('filtered')
    expect(result.traceId).toBe('qtr_1')
    const html = renderToStaticMarkup(<SearchAudit result={result} />)
    expect(html).toContain('không có quyền xem')
    expect(html).toContain('mode')
  })

  it('stays silent when nothing was filtered and no retrieval info exists', () => {
    const result = normalizeAi2SearchResult(
      { hits: [], acl_decision: 'passed' },
      'dos_1',
    )
    expect(renderToStaticMarkup(<SearchAudit result={result} />)).toBe('')
  })
})

describe('search audit blocked state', () => {
  it('says the query was blocked instead of "nothing found"', () => {
    const result = normalizeAi2SearchResult(
      {
        state: 'BLOCKED',
        hits: [],
        retrieval_layer: { selected: 'NONE' },
      },
      'dos_1',
    )
    const html = renderToStaticMarkup(<SearchAudit result={result} />)
    expect(html).toContain('BLOCKED')
    expect(html).not.toContain('không tìm thấy đoạn nào')
  })
})
