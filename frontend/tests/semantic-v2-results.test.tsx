import { describe, expect, it } from 'vitest'
import { decodeSemanticResults } from '../src/api/semanticResults'

function fixture() {
  const source = (document: string) => ({
    document_id: document,
    snapshot_id: `snapshot-${document}`,
    source_ref: `node-${document}`,
    raw: 'Bên A phải thanh toán',
    citation: {
      node_id: `node-${document}`,
      page_revision_id: `page-${document}`,
      text_span: 'Bên A phải thanh toán',
      source_file_id: document,
      page: 1,
      line_ids: ['line-1'],
      char_start: 0,
      char_end: 20,
      validation_status: 'VALID',
    },
  })
  const frame = (id: string, document: string) => ({
    frame_id: id,
    family: 'OBLIGATION',
    profile: 'SALES',
    document_id: document,
    snapshot_id: `snapshot-${document}`,
    dossier_id: 'dossier',
    evidence: [source(document)],
    slots: {
      action: {
        value_type: 'TEXT',
        value: 'PAY',
        state: 'GROUNDED',
        evidence: [source(document)],
        reason: '',
      },
    },
    key: {
      key: ['A', 'PAY', 'OBLIGATION', 'REQUIRED'],
      certainty: 'DEFINITE',
      reason: 'closed symbols',
      method: 'CLOSED_SYMBOL',
      alias_digest: null,
      alias_version: null,
      alias_proposal_ids: [],
    },
  })
  const left = frame('left', 'body')
  const right = frame('right', 'annex')
  return {
    dossier_id: 'dossier',
    run_id: 'run-1',
    result_digest: 'a'.repeat(64),
    state: 'NEEDS_REVIEW',
    reason: null,
    semantic_extension: {
      schema_version: 'ai2.semantic.v1',
      tenant_id: 'tenant',
      dossier_id: 'dossier',
      profile_digest: 'b'.repeat(64),
      alias_version: 0,
      alias_digest: null,
      frames: [left, right],
      rows: ['left', 'right'],
      pairs: [
        {
          pair_id: 'pair-1',
          left_id: 'left',
          right_id: 'right',
          disposition: 'CONFLICT_CANDIDATE',
          reason: 'opposite modality',
          left_evidence: left.evidence,
          right_evidence: right.evidence,
          review_state: 'NEEDS_REVIEW',
          method: 'CLOSED_SYMBOL',
          candidate_sources: ['SEMANTIC_ALIGNMENT'],
          alignment_key: ['PAY', 'scope:invoice'],
          conflict_kind: 'SEMANTIC_CONFLICT',
          slots_in_difference: ['modality_negation'],
        },
      ],
      timeline: [],
      alias_drafts: [],
      coverage: {
        state: 'NEEDS_REVIEW',
        attempted_nodes: 2,
        frames: 2,
        grounded_slots: 2,
        unresolved_slots: 0,
        invalid_evidence: 0,
        reasons: ['partial_context'],
        context_nodes: 0,
        context_calls: 0,
        by_family: {},
        by_slot: {},
        by_output: {},
      },
    },
  }
}

describe('semantic v2 result diagnostics', () => {
  it('keeps conflict kind, alignment key, and changed slots', () => {
    const result = decodeSemanticResults(fixture(), 'dossier')
    expect(result.extension?.pairs[0]).toMatchObject({
      conflict_kind: 'SEMANTIC_CONFLICT',
      alignment_key: ['PAY', 'scope:invoice'],
      slots_in_difference: ['modality_negation'],
    })
  })
})
