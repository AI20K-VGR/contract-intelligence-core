import { describe, expect, it } from 'vitest'
import { normalizeFact, normalizeFinding } from '../src/api/analysis'

describe('structured contract analysis contracts', () => {
  it('keeps a fact safe when the backend citation is only partial', () => {
    const fact = normalizeFact({
      fact: {
        id: 'fact-1',
        document_id: 'doc-1',
        key: 'contract_value',
        fact_type: 'amount',
        raw_text: '100 tỷ đồng',
        normalized_value: { amount: 100, currency: 'VND' },
        confidence: 0.91,
        citation: { id: 'cit-1', quote: '100 tỷ đồng', segments: [] },
      },
      effective_value: { amount: 100, currency: 'VND' },
      review_state: 'unreviewed',
      current_version: 2,
    })

    expect(fact.key).toBe('contract_value')
    expect(fact.evidence.status).toBe('PARTIAL')
    expect(fact.evidence.citationId).toBe('cit-1')
  })

  it('preserves conflict scope and safe no-evidence state', () => {
    const finding = normalizeFinding({
      id: 'finding-1',
      finding_type: 'comparison',
      scope: 'annex',
      key_or_topic: 'Payment term',
      disposition: 'conflict',
      severity: 'high',
      confidence: 0.7,
      sides: [
        { side: 'contract', document_id: 'doc-1', value_snapshot: '30 days' },
      ],
    })

    expect(finding.scope).toBe('annex')
    expect(finding.sides[0].evidence.status).toBe('UNRESOLVED')
  })
})
