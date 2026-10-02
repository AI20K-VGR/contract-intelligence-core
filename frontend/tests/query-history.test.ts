import { describe, expect, it } from 'vitest'
import { formatDocumentCounts } from '../src/api/dossiers'
import { normalizeQueryHistoryItem } from '../src/api/queries'

describe('normalizeQueryHistoryItem', () => {
  it('reads an answered question with citations', () => {
    const item = normalizeQueryHistoryItem({
      trace_id: 'qtr_1',
      endpoint: 'ask',
      actor_id: 'usr_1',
      question: 'Giá trị hợp đồng?',
      answer: '1.286.400.000 đồng',
      state: 'PASS',
      citations: [{ quote: 'Giá trị: 1.286.400.000', page_no: 3 }],
      error_code: null,
      created_at: '2026-10-01T09:12:00+00:00',
    })
    expect(item?.answer).toBe('1.286.400.000 đồng')
    expect(item?.citations).toEqual([
      { quote: 'Giá trị: 1.286.400.000', pageNo: 3 },
    ])
  })

  it('keeps a failed question with no answer', () => {
    const item = normalizeQueryHistoryItem({
      trace_id: 'qtr_2',
      endpoint: 'query',
      actor_id: 'usr_1',
      question: 'Hỏi lỗi',
      answer: null,
      state: null,
      citations: [],
      error_code: 'AI2_TIMEOUT',
      created_at: '2026-10-01T09:13:00+00:00',
    })
    expect(item?.answer).toBeNull()
    expect(item?.errorCode).toBe('AI2_TIMEOUT')
    expect(item?.endpoint).toBe('query')
  })

  it('drops rows without a trace id', () => {
    expect(normalizeQueryHistoryItem({ question: 'x' })).toBeNull()
    expect(normalizeQueryHistoryItem(null)).toBeNull()
  })
})

describe('formatDocumentCounts', () => {
  it('lists contracts and annexes, skipping zeros', () => {
    expect(formatDocumentCounts({ contracts: 1, annexes: 3 })).toBe(
      '1 hợp đồng · 3 phụ lục',
    )
    expect(formatDocumentCounts({ contracts: 1, annexes: 0 })).toBe('1 hợp đồng')
    expect(formatDocumentCounts({ contracts: 0, annexes: 0 })).toBe('')
  })
})
