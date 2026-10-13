import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import {
  decodeSemanticResults,
  decodeFindingSemantic,
} from '../src/api/semanticResults'
import { ClauseFrameResults } from '../src/components/ClauseFrameResults'

export function semanticFixture() {
  const evidence = (document: string) => ({
    document_id: document,
    snapshot_id: `snapshot-${document}`,
    source_ref: 'line:1:l1#span0',
    raw: 'Bên A phải thanh toán',
    citation: {
      node_id: 'line:1:l1',
      page_revision_id: 'page1',
      text_span: 'Bên A phải thanh toán',
      source_file_id: document,
      page: 1,
      line_ids: ['l1'],
      char_start: 0,
      char_end: 23,
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
    evidence: [evidence(document)],
    slots: {
      amount: {
        value_type: 'DECIMAL',
        value: '9007199254740993',
        state: 'GROUNDED',
        evidence: [evidence(document)],
        reason: '',
      },
      condition: {
        value_type: 'NONE',
        value: null,
        state: 'UNKNOWN',
        evidence: [evidence(document)],
        reason: 'not_assessed',
      },
    },
    key: {
      key: null,
      certainty: 'UNKNOWN',
      reason: 'scope_unknown',
      method: 'TENANT_ALIAS',
      alias_digest: 'a'.repeat(64),
      alias_version: 7,
      alias_proposal_ids: ['approved-alias'],
    },
  })
  const frames = [frame('left', 'body'), frame('right', 'annex')]
  return {
    dossier_id: 'dossier',
    run_id: 'run1',
    result_digest: 'b'.repeat(64),
    state: 'NEEDS_REVIEW',
    reason: null,
    semantic_extension: {
      schema_version: 'ai2.semantic.v1',
      tenant_id: 'tenant',
      dossier_id: 'dossier',
      profile_digest: 'c'.repeat(64),
      alias_version: 7,
      alias_digest: 'a'.repeat(64),
      frames,
      rows: ['left', 'right'],
      pairs: [
        {
          pair_id: 'pair1',
          left_id: 'left',
          right_id: 'right',
          disposition: 'SCOPE_DIFFERS',
          reason: 'different_scope',
          left_evidence: frames[0].evidence,
          right_evidence: frames[1].evidence,
          review_state: 'NEEDS_REVIEW',
          method: 'TENANT_ALIAS',
          candidate_sources: ['EXPLICIT_REFERENCE'],
          conflict_kind: 'SEMANTIC_CONFLICT',
          alignment_key: ['PAY', 'scope:invoice'],
          slots_in_difference: ['modality_negation'],
        },
      ],
      timeline: [
        {
          edge_id: 'edge1',
          source_id: 'right',
          target_id: null,
          relation: 'AMENDS',
          date_role: 'SIGNING',
          date_value: '2026-10-03',
          evidence: frames[1].evidence,
          acceptance: null,
          value_slot: 'amount',
          proposed_value: null,
          reasons: ['missing_target', 'effective_date_missing'],
          review_state: 'NEEDS_REVIEW',
        },
      ],
      alias_drafts: [],
      coverage: {
        state: 'NEEDS_REVIEW',
        attempted_nodes: 2,
        frames: 2,
        grounded_slots: 2,
        unresolved_slots: 2,
        invalid_evidence: 0,
        reasons: ['partial'],
        context_nodes: 0,
        context_calls: 0,
        by_family: {
          OBLIGATION: { attempted: 2, covered: 2, review: 2, missing: 0 },
        },
        by_slot: {},
        by_output: {},
      },
    },
  }
}

describe('semantic results closed boundary and projections', () => {
  it('keeps exact decimal, UNKNOWN, paired sources, alias pins and timeline reasons', () => {
    const model = decodeSemanticResults(semanticFixture(), 'dossier')
    expect(model.extension?.frames[0].slots.amount.value).toBe(
      '9007199254740993',
    )
    expect(model.extension?.frames[0].slots.condition.value).toBeNull()
    const html = renderToStaticMarkup(
      <ClauseFrameResults dossierId="dossier" initial={model} />,
    )
    for (const text of [
      'Điều khoản',
      'Cặp nghi vấn',
      'Dòng thời gian',
      '9007199254740993',
      'UNKNOWN',
      'not_assessed',
      'SCOPE_DIFFERS',
      'different_scope',
      'TENANT_ALIAS',
      'body',
      'annex',
      'SIGNING',
      'effective_date_missing',
      'NEEDS_REVIEW',
      'SEMANTIC_CONFLICT',
      'PAY / scope:invoice',
      'modality_negation',
    ]) {
      expect(html).toContain(text)
    }
    expect(html).not.toContain('LEGAL_WINNER')
  })
  it.each([
    'dossier',
    'pair',
    'state',
    'decimal',
    'source',
    'rows',
    'coverage',
  ])('rejects malformed %s without certainty coercion', (kind) => {
    const raw = semanticFixture()
    if (kind === 'dossier') raw.semantic_extension.dossier_id = 'other'
    if (kind === 'pair') raw.semantic_extension.pairs[0].right_id = 'missing'
    if (kind === 'state')
      raw.semantic_extension.timeline[0].review_state = 'PASS'
    if (kind === 'decimal')
      raw.semantic_extension.frames[0].slots.amount.value = 'NaN'
    if (kind === 'source')
      raw.semantic_extension.frames[0].evidence[0].document_id = 'other'
    if (kind === 'rows') raw.semantic_extension.rows = ['left']
    if (kind === 'coverage') raw.semantic_extension.coverage.grounded_slots = -1
    expect(() => decodeSemanticResults(raw, 'dossier')).toThrow()
  })
  it('shows legacy absence as NOT_MEASURED and forbids result/run mismatch', () => {
    const model = decodeSemanticResults(
      {
        dossier_id: 'dossier',
        run_id: 'old',
        state: 'NOT_MEASURED',
        reason: 'LEGACY_EXTENSION_ABSENT',
        semantic_extension: null,
      },
      'dossier',
    )
    expect(
      renderToStaticMarkup(
        <ClauseFrameResults dossierId="dossier" initial={model} />,
      ),
    ).toContain('NOT_MEASURED')
    expect(() =>
      decodeSemanticResults(semanticFixture(), 'dossier', 'another-run'),
    ).toThrow()
    expect(
      renderToStaticMarkup(
        <ClauseFrameResults
          dossierId="dossier"
          initial={decodeSemanticResults(semanticFixture(), 'dossier')}
          expectedRun="another-run"
        />,
      ),
    ).toContain('Lần chạy đã đổi')
  })
  it('preserves typed finding side provenance without inferring semantic state from severity', () => {
    const extension = semanticFixture().semantic_extension
    const semantic = decodeFindingSemantic({
      frame: extension.frames[0],
      pair: extension.pairs[0],
      profile_digest: extension.profile_digest,
      alias_version: 7,
      alias_digest: extension.alias_digest,
      alignment_key: ['PAY', 'scope:invoice'],
      conflict_kind: 'SEMANTIC_CONFLICT',
      slots_in_difference: ['modality_negation'],
    })
    expect(semantic?.pair?.disposition).toBe('SCOPE_DIFFERS')
    expect(semantic?.alignment_key).toEqual(['PAY', 'scope:invoice'])
    expect(semantic?.conflict_kind).toBe('SEMANTIC_CONFLICT')
    expect(semantic?.slots_in_difference).toEqual(['modality_negation'])
    expect(semantic?.frame.slots.amount.value).toBe('9007199254740993')
    expect(decodeFindingSemantic(undefined)).toBeNull()
    expect(() =>
      decodeFindingSemantic({
        ...semantic,
        pair: { ...extension.pairs[0], disposition: 'INVENTED' },
      }),
    ).toThrow()
  })
  it('opens authenticated source through the existing client with exact location', async () => {
    const fetch = vi.fn(
      async () => new Response(new Blob(['image']), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetch)
    const { fetchSemanticSource } = await import('../src/api/semanticResults')
    const evidence = decodeSemanticResults(semanticFixture(), 'dossier')
      .extension!.frames[0].evidence[0]
    const blob = await fetchSemanticSource(evidence)
    expect(blob.size).toBeGreaterThan(0)
    expect(fetch.mock.calls[0][0]).toContain(
      '/api/v1/documents/body/pages/1/image',
    )
    expect(fetch.mock.calls[0][1]?.headers).toBeInstanceOf(Headers)
    vi.unstubAllGlobals()
  })
})
