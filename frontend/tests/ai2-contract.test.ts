import { describe, expect, it } from 'vitest'
import fixtures from './fixtures/ai2-responses.json'
import {
  normalizeAi2SearchResult,
  type Ai2PipelineStatus,
} from '../src/api/ai2'

describe('AI2 contract normalization', () => {
  it('preserves locatable citation metadata and derives answered state', () => {
    const result = normalizeAi2SearchResult(
      fixtures.answered,
      'dos_01M38T3PD2Z45CJXGS6FQGKSWX',
    )

    expect(result.dossierId).toBe('dos_01M38T3PD2Z45CJXGS6FQGKSWX')
    expect(result.reviewState).toBe('ANSWERED')
    expect(result.hits[0].citation.status).toBe('LOCATABLE')
    expect(result.hits[0].citation.lineId).toBe(
      'line:3:doc-contract:s1:p003:l002',
    )
  })

  it('fails closed for an unresolved citation', () => {
    const result = normalizeAi2SearchResult(
      fixtures.unresolved,
      'dos_01M38T3PD2Z45CJXGS6FQGKSWX',
    )

    expect(result.hits[0].citation.status).toBe('UNRESOLVED')
    expect(result.reviewState).toBe('NEEDS_REVIEW')
  })

  it('rejects an empty dossier scope', () => {
    expect(() => normalizeAi2SearchResult({}, '')).toThrow(
      'dossier scope is required',
    )
  })

  it('keeps pipeline status and bounded error fields typed', () => {
    const status: Ai2PipelineStatus = {
      dossierId: 'dos_01M38T3PD2Z45CJXGS6FQGKSWX',
      runId: 'run-1',
      status: 'FAILED',
      errorCode: 'MISTRAL_API_KEY_MISSING',
      errorMessage: 'MISTRAL_API_KEY is not set',
      steps: [],
    }

    expect(status.errorCode).toBe('MISTRAL_API_KEY_MISSING')
  })
})
