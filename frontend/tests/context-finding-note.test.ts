import { describe, expect, it } from 'vitest'
import { contextPanelModel } from '../src/components/DossierAnalysisPanel'
import type { Ai2Analysis } from '../src/api/analysis'

function analysisWith(findings: unknown[]): Ai2Analysis {
  return {
    dossierId: 'dos-1',
    runId: 'run-1',
    available: true,
    pipelineStatus: 'SUCCEEDED',
    jobStatus: 'SUCCEEDED',
    reviewState: 'NEEDS_REVIEW',
    completenessState: 'PARTIAL',
    reasonCode: null,
    evidenceReady: false,
    inputCounts: {},
    outputCounts: {},
    coverage: {},
    droppedRecords: 0,
    evidenceIssueCount: 0,
    contextFindings: findings,
    evidenceIssues: [],
  }
}

describe('context finding relation note', () => {
  it('shows UNCONFIRMED from context finding metadata', () => {
    const model = contextPanelModel(
      analysisWith([
        {
          finding_id: 'gap-1',
          kind: 'CONTEXT_GAP',
          reason: 'Phụ lục 01 chưa được thân nhắc tên.',
          review_state: 'NEEDS_REVIEW',
          metadata: { relation: 'UNCONFIRMED', item_key: 'contract_value' },
        },
      ]),
      [],
      [],
    )
    expect(model.contextFindings[0]?.relation).toBe('UNCONFIRMED')
    expect(model.contextFindings[0]?.reasonCode).toBe('CONTEXT_GAP')
    expect(model.contextFindings[0]?.subject).toContain('Phụ lục 01')
  })
})
