import { apiFetch, ApiError } from './client'

export type LexiconAction =
  | 'ASSIGN'
  | 'PROPOSE'
  | 'APPROVE'
  | 'REJECT'
  | 'REVOKE'
  | 'OPT_IN'
  | 'PROMOTE'
  | 'MEASURE'
export type LexiconCommand = {
  action: LexiconAction
  base_version: number
  idempotency_key: string
  payload: Record<string, unknown>
}
export type LexiconProposal = {
  proposal_id: string
  producer_id: string
  source: string
  symbol: string
  kind: 'action' | 'qualifier'
  source_ref: string
}
export type LexiconProfile = {
  tenant_id: string
  version: number
  aliases: Record<string, unknown>[]
  active_aliases: Record<string, unknown>[]
  proposals: LexiconProposal[]
  decisions: Record<string, string>
  measurements: Record<string, unknown>
  opt_in: boolean
  activation_state: 'ACTIVE' | 'DRAFT_ONLY'
  activation_blockers: string[]
  digest?: string
  [key: string]: unknown
}
export type LexiconPermissions = Record<
  | 'can_propose'
  | 'can_assign'
  | 'can_approve'
  | 'can_reject'
  | 'can_revoke'
  | 'can_opt_in'
  | 'can_measure'
  | 'can_promote',
  boolean
>
export type LexiconModel = {
  profile: LexiconProfile
  assignment: {
    expert_id: string
    expertise_ref: string
    expires_at: string
    designated_by: string
  } | null
  permissions: LexiconPermissions
}
export type LexiconReceipt = {
  version: number
  activation_state: 'ACTIVE' | 'DRAFT_ONLY'
  activation_blockers: string[]
}
export class LexiconConflictError extends Error {
  readonly current: LexiconModel | null
  constructor(current: LexiconModel | null) {
    super('Phiên bản đã đổi. Hãy xem bản mới trước khi gửi lại quyết định.')
    this.current = current
  }
}
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Lexicon object không hợp lệ.')
  return value as Record<string, unknown>
}
function string(value: unknown): string {
  if (typeof value !== 'string' || !value.trim())
    throw new Error('Lexicon text không hợp lệ.')
  return value
}
function integer(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0)
    throw new Error('Lexicon version không hợp lệ.')
  return value
}
function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean')
    throw new Error('Thiếu quyền đã xác minh từ server.')
  return value
}
function list<T>(value: unknown, decode: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) throw new Error('Lexicon list không hợp lệ.')
  return value.map(decode)
}
function activation(value: unknown): 'ACTIVE' | 'DRAFT_ONLY' {
  if (value !== 'ACTIVE' && value !== 'DRAFT_ONLY')
    throw new Error('Activation state không hợp lệ.')
  return value
}
export function decodeLexicon(value: unknown, tenantId: string): LexiconModel {
  const envelope = record(value),
    raw = record(envelope.data),
    metadata = record(envelope.metadata),
    permissions = record(metadata.permissions)
  if (raw.tenant_id !== tenantId) throw new Error('Lexicon thuộc tenant khác.')
  const profile: LexiconProfile = {
    ...raw,
    tenant_id: tenantId,
    version: integer(raw.version),
    aliases: list(raw.aliases, record),
    active_aliases: list(raw.active_aliases, record),
    proposals: list(raw.proposals, (v) => {
      const p = record(v)
      if (p.kind !== 'action' && p.kind !== 'qualifier')
        throw new Error('Alias kind không hợp lệ.')
      return {
        proposal_id: string(p.proposal_id),
        producer_id: string(p.producer_id),
        source: string(p.source),
        symbol: string(p.symbol),
        kind: p.kind,
        source_ref: string(p.source_ref),
      }
    }),
    decisions: Object.fromEntries(
      Object.entries(record(raw.decisions)).map(([key, v]) => [key, string(v)]),
    ),
    measurements: record(raw.measurements),
    opt_in: boolean(raw.opt_in),
    activation_state: activation(raw.activation_state),
    activation_blockers: list(raw.activation_blockers, string),
  }
  if (
    profile.activation_state === 'DRAFT_ONLY' &&
    profile.active_aliases.length
  )
    throw new Error('Draft profile chứa active aliases.')
  const permissionKeys = [
    'can_propose',
    'can_assign',
    'can_approve',
    'can_reject',
    'can_revoke',
    'can_opt_in',
    'can_measure',
    'can_promote',
  ] as const
  const trusted = Object.fromEntries(
    permissionKeys.map((key) => [key, boolean(permissions[key])]),
  ) as LexiconPermissions
  let assignment: LexiconModel['assignment'] = null
  if (metadata.assignment !== null) {
    const a = record(metadata.assignment)
    assignment = {
      expert_id: string(a.expert_id),
      expertise_ref: string(a.expertise_ref),
      expires_at: string(a.expires_at),
      designated_by: string(a.designated_by),
    }
    if (Number.isNaN(Date.parse(assignment.expires_at)))
      throw new Error('Expert expiry không hợp lệ.')
  }
  return { profile, assignment, permissions: trusted }
}
async function fetchEnvelope(
  path: string,
  init: RequestInit = {},
): Promise<unknown> {
  const response = await apiFetch(path, init)
  const body: unknown = await response.json()
  if (!response.ok) {
    const raw = record(body),
      detail = typeof raw.detail === 'object' ? record(raw.detail) : {}
    throw new ApiError(
      response.status,
      typeof detail.code === 'string'
        ? detail.code
        : `Lexicon API ${response.status}`,
      typeof detail.code === 'string' ? detail.code : undefined,
      body,
    )
  }
  return body
}
export async function getTenantLexicon(
  tenantId: string,
  signal?: AbortSignal,
  version?: number,
): Promise<LexiconModel> {
  return decodeLexicon(
    await fetchEnvelope(
      `/api/v1/tenants/${encodeURIComponent(tenantId)}/lexicon${version ? `?version=${version}` : ''}`,
      { signal },
    ),
    tenantId,
  )
}
export async function submitLexiconCommand(
  tenantId: string,
  command: LexiconCommand,
): Promise<LexiconReceipt> {
  if (
    !Number.isSafeInteger(command.base_version) ||
    command.base_version < 0 ||
    !command.idempotency_key.trim()
  )
    throw new Error('Lệnh thiếu version/idempotency.')
  let envelope: unknown
  try {
    envelope = await fetchEnvelope(
      `/api/v1/tenants/${encodeURIComponent(tenantId)}/lexicon/commands`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(command),
      },
    )
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      let current: LexiconModel | null = null
      try {
        current = await getTenantLexicon(tenantId)
      } catch {
        /* Conflict remains blocked if profile refresh fails. */
      }
      throw new LexiconConflictError(current)
    }
    throw error
  }
  const receipt = record(record(envelope).data)
  return {
    version: integer(receipt.version),
    activation_state: activation(receipt.activation_state),
    activation_blockers: list(receipt.activation_blockers, string),
  }
}
