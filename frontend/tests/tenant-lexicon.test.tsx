import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  decodeLexicon,
  submitLexiconCommand,
  LexiconConflictError,
} from '../src/api/tenantLexicon'
import { TenantLexiconPanel } from '../src/components/TenantLexiconPanel'

export function lexiconFixture() {
  return {
    data: {
      tenant_id: 'tenant',
      version: 2,
      aliases: [],
      active_aliases: [],
      proposals: [
        {
          proposal_id: 'p1',
          producer_id: 'producer',
          source: 'chi trả',
          symbol: 'PAY',
          kind: 'action',
          source_ref: 'line1',
        },
      ],
      decisions: { p1: 'PROPOSED' },
      measurements: {},
      opt_in: false,
      activation_state: 'DRAFT_ONLY',
      activation_blockers: ['POLICY_NOT_FROZEN'],
    },
    metadata: {
      assignment: {
        expert_id: 'expert',
        expertise_ref: 'designation',
        expires_at: '2027-01-01T00:00:00Z',
        designated_by: 'admin',
      },
      permissions: {
        can_propose: false,
        can_assign: false,
        can_approve: true,
        can_reject: true,
        can_revoke: true,
        can_opt_in: false,
        can_measure: true,
        can_promote: false,
      },
    },
  }
}
afterEach(() => vi.unstubAllGlobals())
describe('tenant lexicon governance consumer', () => {
  it('uses trusted permissions, preserves missing activation policy and version history', () => {
    const model = decodeLexicon(lexiconFixture(), 'tenant')
    const html = renderToStaticMarkup(
      <TenantLexiconPanel tenantId="tenant" actorId="expert" initial={model} />,
    )
    for (const text of [
      'DRAFT_ONLY',
      'POLICY_NOT_FROZEN',
      'chi trả',
      'PAY',
      'Duyệt',
      'Từ chối',
      'Phiên bản 2',
      'lần chạy mới',
    ])
      expect(html).toContain(text)
    expect(model.permissions.can_promote).toBe(false)
    expect(model.profile.active_aliases).toEqual([])
  })
  it('never gives a generic admin approval when named expert assignment is absent', () => {
    const raw = lexiconFixture()
    const model = decodeLexicon(
      {
        ...raw,
        metadata: {
          assignment: null,
          permissions: {
            ...raw.metadata.permissions,
            can_approve: false,
            can_reject: false,
            can_revoke: false,
          },
        },
      },
      'tenant',
    )
    expect(
      renderToStaticMarkup(
        <TenantLexiconPanel
          tenantId="tenant"
          actorId="admin"
          initial={model}
        />,
      ),
    ).not.toContain('>Duyệt</button>')
    expect(() =>
      decodeLexicon(
        { ...raw, data: { ...raw.data, tenant_id: 'other' } },
        'tenant',
      ),
    ).toThrow()
  })
  it('rejects missing trusted permission booleans', () => {
    const raw = lexiconFixture()
    expect(() =>
      decodeLexicon(
        { ...raw, metadata: { assignment: null, permissions: {} } },
        'tenant',
      ),
    ).toThrow()
  })
  it('sends explicit CAS/idempotency command and exposes receipt without activation inference', async () => {
    const fetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            data: {
              version: 3,
              activation_state: 'DRAFT_ONLY',
              activation_blockers: ['POLICY_NOT_FROZEN'],
            },
          }),
          { status: 200 },
        ),
    )
    vi.stubGlobal('fetch', fetch)
    const receipt = await submitLexiconCommand('tenant', {
      action: 'APPROVE',
      base_version: 2,
      idempotency_key: 'same-command',
      payload: { proposal_id: 'p1' },
    })
    expect(receipt.activation_state).toBe('DRAFT_ONLY')
    const init = fetch.mock.calls[0][1]
    expect(JSON.parse(String(init?.body))).toEqual({
      action: 'APPROVE',
      base_version: 2,
      idempotency_key: 'same-command',
      payload: { proposal_id: 'p1' },
    })
  })
  it('409 refreshes authoritative profile once and never auto retries the changed decision', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ detail: { code: 'LEXICON_VERSION_CONFLICT' } }),
          { status: 409 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ...lexiconFixture(),
            data: { ...lexiconFixture().data, version: 3 },
          }),
          { status: 200 },
        ),
      )
    vi.stubGlobal('fetch', fetch)
    let conflict: unknown
    try {
      await submitLexiconCommand('tenant', {
        action: 'APPROVE',
        base_version: 2,
        idempotency_key: 'old',
        payload: { proposal_id: 'p1' },
      })
    } catch (error) {
      conflict = error
    }
    expect(conflict).toBeInstanceOf(LexiconConflictError)
    expect((conflict as LexiconConflictError).current?.profile.version).toBe(3)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(
      fetch.mock.calls.filter(([, init]) => init?.method === 'POST'),
    ).toHaveLength(1)
  })
})
