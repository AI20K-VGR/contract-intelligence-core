import { describe, expect, it } from 'vitest'
import { normalizeAi2SearchResult } from '../src/api/ai2'

describe('AI2 query state passthrough', () => {
  it('keeps server state and operational trace', () => {
    const result = normalizeAi2SearchResult(
      {
        state: 'PASS',
        answer: 'answer text',
        connected: true,
        used_llm: false,
        retrieval_layer: { selected: 'LEXICAL' },
        reasoning_trace: [{ code: 'LEXICAL_RETRIEVAL' }],
        hits: [{ text: 'evidence', node_id: 'n1' }],
      },
      'dos_1',
    )

    expect(result.reviewState).toBe('PASS')
    expect(result.retrievalLayer.selected).toBe('LEXICAL')
    expect(result.reasoningTrace).toEqual([{ code: 'LEXICAL_RETRIEVAL' }])
    expect(result.usedLlm).toBe(false)
  })

  it('does not infer answered from answer and hits', () => {
    const result = normalizeAi2SearchResult(
      { answer: 'looks complete', connected: true, hits: [{ text: 'evidence' }] },
      'dos_1',
    )

    expect(result.reviewState).not.toBe('ANSWERED')
  })
})
