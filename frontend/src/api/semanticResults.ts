import { apiFetch, getJson } from './client'

export const SEMANTIC_DISPOSITIONS = [
  'DUPLICATE',
  'COMPARABLE_DIFFERENCE',
  'NOT_COMPARABLE',
  'GENERAL_VS_SPECIFIC',
  'SCOPE_DIFFERS',
  'NEEDS_REVIEW_UNPARSED',
  'NEEDS_REVIEW_BACKOFF',
  'GRADUATED',
  'CUMULATIVE',
  'CONFLICT_CANDIDATE',
] as const
export type SemanticDisposition = (typeof SEMANTIC_DISPOSITIONS)[number]
export type SemanticEvidence = {
  document_id: string
  snapshot_id: string
  source_ref: string
  raw: string
  citation: {
    source_file_id: string | null
    page: number | null
    line_ids: string[]
    text_span: string
    validation_status: string
    char_start: number | null
    char_end: number | null
    [key: string]: unknown
  }
}
export type SemanticSlot = {
  value_type: 'DECIMAL' | 'TEXT' | 'NONE'
  value: string | null
  state: 'GROUNDED' | 'UNKNOWN' | 'ABSENT' | 'UNSUPPORTED'
  evidence: SemanticEvidence[]
  reason: string
}
export type SemanticFrame = {
  frame_id: string
  family: string
  profile: string
  document_id: string
  snapshot_id: string
  dossier_id: string
  evidence: SemanticEvidence[]
  slots: Record<string, SemanticSlot>
  key: {
    key: string[] | null
    certainty: 'DEFINITE' | 'UNKNOWN'
    reason: string
    method: 'CLOSED_SYMBOL' | 'TENANT_ALIAS'
    alias_digest: string | null
    alias_version: number | null
    alias_proposal_ids: string[]
  }
}
export type SemanticPair = {
  pair_id: string
  left_id: string
  right_id: string
  disposition: SemanticDisposition
  reason: string
  left_evidence: SemanticEvidence[]
  right_evidence: SemanticEvidence[]
  review_state: 'NEEDS_REVIEW'
  method: 'CLOSED_SYMBOL' | 'TENANT_ALIAS'
  candidate_sources: string[]
  alignment_key?: string[] | null
  conflict_kind?: 'SEMANTIC_CONFLICT' | 'ARITHMETIC_INCONSISTENCY' | 'AMENDMENT_REVIEW' | 'COMPARABLE_DIFFERENCE' | null
  slots_in_difference?: string[]
}
export type SemanticTimeline = {
  edge_id: string
  source_id: string
  target_id: string | null
  relation: 'REFERENCES' | 'AMENDS'
  date_role: 'EFFECTIVE' | 'SIGNING' | 'UNKNOWN'
  date_value: string | null
  evidence: SemanticEvidence[]
  acceptance: SemanticSlot | null
  value_slot: string | null
  proposed_value: SemanticSlot | null
  reasons: string[]
  review_state: 'NEEDS_REVIEW'
}
export type CoverageCounts = {
  attempted: number
  covered: number
  review: number
  missing: number
}
export type SemanticExtension = {
  schema_version: 'ai2.semantic.v1'
  tenant_id: string
  dossier_id: string
  profile_digest: string
  alias_version: number
  alias_digest: string | null
  frames: SemanticFrame[]
  rows: string[]
  pairs: SemanticPair[]
  timeline: SemanticTimeline[]
  alias_drafts: {
    source: string
    symbol: string
    kind: 'action' | 'qualifier'
    source_ref: string
    status: 'DRAFT'
  }[]
  typed_table_projections?: {
    payment_schedules: Record<string, unknown>[]
    boq_checks: Record<string, unknown>[]
  }
  coverage: {
    state: 'NEEDS_REVIEW' | 'NOT_MEASURED'
    attempted_nodes: number
    frames: number
    grounded_slots: number
    unresolved_slots: number
    invalid_evidence: number
    reasons: string[]
    context_nodes: number
    context_calls: number
    by_family: Record<string, CoverageCounts>
    by_slot: Record<string, CoverageCounts>
    by_output: Record<string, CoverageCounts>
  }
}
export type SemanticResults = {
  dossierId: string
  runId: string | null
  resultDigest: string | null
  state: 'NEEDS_REVIEW' | 'NOT_MEASURED' | 'NOT_READY'
  reason: string | null
  extension: SemanticExtension | null
  typedTableProjections?: { payment_schedules: Record<string, unknown>[]; boq_checks: Record<string, unknown>[] }
}
export type FindingSemantic = {
  frame: SemanticFrame
  pair: SemanticPair | null
  timeline: SemanticTimeline | null
  profile_digest: string
  alias_version: number
  alias_digest: string | null
  alignment_key?: string[] | null
  conflict_kind?: 'SEMANTIC_CONFLICT' | 'ARITHMETIC_INCONSISTENCY' | 'AMENDMENT_REVIEW' | 'COMPARABLE_DIFFERENCE' | null
  slots_in_difference?: string[]
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Semantic object không hợp lệ.')
  return value as Record<string, unknown>
}
function text(value: unknown, empty = false): string {
  if (typeof value !== 'string' || (!empty && !value.trim()))
    throw new Error('Semantic text không hợp lệ.')
  return value
}
function nullableText(value: unknown): string | null {
  return value === null ? null : text(value)
}
function integer(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0)
    throw new Error('Semantic count không hợp lệ.')
  return value
}
function array<T>(value: unknown, decode: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) throw new Error('Semantic list không hợp lệ.')
  return value.map(decode)
}
function choice<T extends string>(value: unknown, choices: readonly T[]): T {
  if (!choices.includes(value as T))
    throw new Error('Semantic enum không được hỗ trợ.')
  return value as T
}
function hash(value: unknown): string {
  const result = text(value)
  if (!/^[a-f0-9]{64}$/.test(result))
    throw new Error('Semantic digest không hợp lệ.')
  return result
}
function evidence(value: unknown): SemanticEvidence {
  const row = record(value),
    citation = record(row.citation)
  const result = {
    document_id: text(row.document_id),
    snapshot_id: text(row.snapshot_id),
    source_ref: text(row.source_ref),
    raw: text(row.raw),
    citation: {
      ...citation,
      source_file_id: nullableText(citation.source_file_id),
      page: citation.page === null ? null : integer(citation.page),
      line_ids: array(citation.line_ids, (v) => text(v)),
      text_span: text(citation.text_span, true),
      validation_status: text(citation.validation_status),
      char_start:
        citation.char_start === null ? null : integer(citation.char_start),
      char_end: citation.char_end === null ? null : integer(citation.char_end),
    },
  }
  if (result.citation.source_file_id !== result.document_id)
    throw new Error('Citation nằm ngoài tài liệu.')
  return result
}
function slot(value: unknown): SemanticSlot {
  const row = record(value)
  const result: SemanticSlot = {
    value_type: choice(row.value_type, ['DECIMAL', 'TEXT', 'NONE']),
    value: row.value === null ? null : text(row.value),
    state: choice(row.state, ['GROUNDED', 'UNKNOWN', 'ABSENT', 'UNSUPPORTED']),
    evidence: array(row.evidence, evidence),
    reason: text(row.reason, true),
  }
  if ((result.value_type === 'NONE') !== (result.value === null))
    throw new Error('Slot type/value không khớp.')
  if (
    result.value_type === 'DECIMAL' &&
    !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(result.value!)
  )
    throw new Error('Decimal không hợp lệ.')
  if (result.state === 'GROUNDED' && (!result.value || !result.evidence.length))
    throw new Error('Thiếu chứng cứ cho grounded slot.')
  if (
    result.state === 'ABSENT' &&
    (result.value !== null || !result.evidence.length)
  )
    throw new Error('ABSENT thiếu chứng cứ.')
  return result
}
const SLOT_NAMES = [
  'actor',
  'beneficiary',
  'action',
  'qualifier',
  'modality_negation',
  'object_scope',
  'condition',
  'exception',
  'temporal_trigger',
  'deadline',
  'deadline_unit',
  'amount',
  'currency',
  'unit',
  'base',
  'period',
  'parameter',
  'definition',
]
function frame(value: unknown): SemanticFrame {
  const row = record(value),
    key = record(row.key),
    slots = record(row.slots)
  if (Object.keys(slots).some((name) => !SLOT_NAMES.includes(name)))
    throw new Error('Slot chưa được hỗ trợ.')
  const result: SemanticFrame = {
    frame_id: text(row.frame_id),
    family: choice(row.family, [
      'OBLIGATION',
      'RIGHT',
      'PROHIBITION',
      'REMEDY',
      'PARAMETER',
      'DEFINITION',
    ]),
    profile: text(row.profile),
    document_id: text(row.document_id),
    snapshot_id: text(row.snapshot_id),
    dossier_id: text(row.dossier_id),
    evidence: array(row.evidence, evidence),
    slots: Object.fromEntries(
      Object.entries(slots).map(([name, value]) => [name, slot(value)]),
    ),
    key: {
      key: key.key === null ? null : array(key.key, (v) => text(v)),
      certainty: choice(key.certainty, ['DEFINITE', 'UNKNOWN']),
      reason: text(key.reason, true),
      method: choice(key.method, ['CLOSED_SYMBOL', 'TENANT_ALIAS']),
      alias_digest: key.alias_digest === null ? null : hash(key.alias_digest),
      alias_version:
        key.alias_version === null ? null : integer(key.alias_version),
      alias_proposal_ids: array(key.alias_proposal_ids, (v) => text(v)),
    },
  }
  if (
    !result.evidence.length ||
    [
      ...result.evidence,
      ...Object.values(result.slots).flatMap((s) => s.evidence),
    ].some(
      (e) =>
        e.document_id !== result.document_id ||
        e.snapshot_id !== result.snapshot_id,
    )
  )
    throw new Error('Frame/source scope không khớp.')
  return result
}
function pair(value: unknown): SemanticPair {
  const row = record(value)
  const result: SemanticPair = {
    pair_id: text(row.pair_id),
    left_id: text(row.left_id),
    right_id: text(row.right_id),
    disposition: choice(row.disposition, SEMANTIC_DISPOSITIONS),
    reason: text(row.reason, true),
    left_evidence: array(row.left_evidence, evidence),
    right_evidence: array(row.right_evidence, evidence),
    review_state: choice(row.review_state, ['NEEDS_REVIEW']),
    method: choice(row.method, ['CLOSED_SYMBOL', 'TENANT_ALIAS']),
    candidate_sources: array(row.candidate_sources, (v) => text(v)),
    alignment_key: row.alignment_key === null || row.alignment_key === undefined ? null : array(row.alignment_key, (v) => text(v)),
    conflict_kind: row.conflict_kind === null || row.conflict_kind === undefined ? null : choice(row.conflict_kind, ['SEMANTIC_CONFLICT', 'ARITHMETIC_INCONSISTENCY', 'AMENDMENT_REVIEW', 'COMPARABLE_DIFFERENCE']),
    slots_in_difference: row.slots_in_difference === undefined ? [] : array(row.slots_in_difference, (v) => text(v)),
  }
  if (
    !result.left_evidence.length ||
    !result.right_evidence.length ||
    result.left_id === result.right_id
  )
    throw new Error('Cặp thiếu hai nguồn.')
  return result
}
function timeline(value: unknown): SemanticTimeline {
  const row = record(value)
  const result: SemanticTimeline = {
    edge_id: text(row.edge_id),
    source_id: text(row.source_id),
    target_id: nullableText(row.target_id),
    relation: choice(row.relation, ['REFERENCES', 'AMENDS']),
    date_role: choice(row.date_role, ['EFFECTIVE', 'SIGNING', 'UNKNOWN']),
    date_value: nullableText(row.date_value),
    evidence: array(row.evidence, evidence),
    acceptance: row.acceptance === null ? null : slot(row.acceptance),
    value_slot: nullableText(row.value_slot),
    proposed_value:
      row.proposed_value === null ? null : slot(row.proposed_value),
    reasons: array(row.reasons, (v) => text(v)),
    review_state: choice(row.review_state, ['NEEDS_REVIEW']),
  }
  if (
    !result.evidence.length ||
    (result.date_value !== null &&
      (!/^\d{4}-\d{2}-\d{2}$/.test(result.date_value) ||
        Number.isNaN(Date.parse(result.date_value))))
  )
    throw new Error('Timeline evidence/date không hợp lệ.')
  if (
    result.proposed_value &&
    (result.relation !== 'AMENDS' ||
      result.date_role !== 'EFFECTIVE' ||
      !result.date_value ||
      !result.target_id ||
      result.acceptance?.state !== 'GROUNDED' ||
      result.acceptance.value !== 'ACCEPTED' ||
      result.proposed_value.state !== 'GROUNDED')
  )
    throw new Error('Timeline proposed value chưa đủ chứng cứ.')
  return result
}
function groups(value: unknown): Record<string, CoverageCounts> {
  return Object.fromEntries(
    Object.entries(record(value)).map(([name, raw]) => {
      const row = record(raw),
        result = {
          attempted: integer(row.attempted),
          covered: integer(row.covered),
          review: integer(row.review),
          missing: integer(row.missing),
        }
      if (
        Object.keys(row).length !== 4 ||
        [result.covered, result.review, result.missing].some(
          (n) => n > result.attempted,
        )
      )
        throw new Error('Coverage denominator không khớp.')
      return [name, result]
    }),
  )
}
export function decodeSemanticResults(
  value: unknown,
  dossierId: string,
  expectedRun?: string,
): SemanticResults {
  const row = record(value),
    actualDossier = text(row.dossier_id),
    runId = row.run_id === null ? null : text(row.run_id)
  if (actualDossier !== dossierId || (expectedRun && runId !== expectedRun))
    throw new Error('Kết quả thuộc hồ sơ/lần chạy khác.')
  const state = choice(row.state, ['NEEDS_REVIEW', 'NOT_MEASURED', 'NOT_READY'])
  let extension: SemanticExtension | null = null
  const typedTableProjections = row.typed_table_projections === undefined || row.typed_table_projections === null
    ? { payment_schedules: [], boq_checks: [] }
    : (() => {
        const typed = record(row.typed_table_projections)
        return {
          payment_schedules: array(typed.payment_schedules ?? [], (v) => record(v)),
          boq_checks: array(typed.boq_checks ?? [], (v) => record(v)),
        }
      })()
  if (row.semantic_extension !== null) {
    const raw = record(row.semantic_extension),
      coverage = record(raw.coverage)
    extension = {
      schema_version: choice(raw.schema_version, ['ai2.semantic.v1']),
      tenant_id: text(raw.tenant_id),
      dossier_id: text(raw.dossier_id),
      profile_digest: hash(raw.profile_digest),
      alias_version: integer(raw.alias_version),
      alias_digest: raw.alias_digest === null ? null : hash(raw.alias_digest),
      frames: array(raw.frames, frame),
      rows: array(raw.rows, (v) => text(v)),
      pairs: array(raw.pairs, pair),
      typed_table_projections: raw.typed_table_projections === undefined || raw.typed_table_projections === null ? undefined : (() => {
        const typed = record(raw.typed_table_projections)
        return {
          payment_schedules: array(typed.payment_schedules ?? [], (v) => record(v)),
          boq_checks: array(typed.boq_checks ?? [], (v) => record(v)),
        }
      })(),
      timeline: array(raw.timeline, timeline),
      alias_drafts: array(raw.alias_drafts, (v) => {
        const draft = record(v)
        return {
          source: text(draft.source),
          symbol: text(draft.symbol),
          kind: choice(draft.kind, ['action', 'qualifier']),
          source_ref: text(draft.source_ref),
          status: choice(draft.status, ['DRAFT']),
        }
      }),
      coverage: {
        state: choice(coverage.state, ['NEEDS_REVIEW', 'NOT_MEASURED']),
        attempted_nodes: integer(coverage.attempted_nodes),
        frames: integer(coverage.frames),
        grounded_slots: integer(coverage.grounded_slots),
        unresolved_slots: integer(coverage.unresolved_slots),
        invalid_evidence: integer(coverage.invalid_evidence),
        reasons: array(coverage.reasons, (v) => text(v)),
        context_nodes: integer(coverage.context_nodes),
        context_calls: integer(coverage.context_calls),
        by_family: groups(coverage.by_family),
        by_slot: groups(coverage.by_slot),
        by_output: groups(coverage.by_output),
      },
    }
    const frames = new Map(extension.frames.map((f) => [f.frame_id, f]))
    if (
      state !== 'NEEDS_REVIEW' ||
      !runId ||
      extension.dossier_id !== dossierId ||
      frames.size !== extension.frames.length ||
      new Set(extension.rows).size !== frames.size ||
      extension.rows.some((id) => !frames.has(id)) ||
      extension.frames.some(
        (f) =>
          f.dossier_id !== dossierId ||
          (f.key.method === 'TENANT_ALIAS' &&
            (f.key.alias_digest !== extension!.alias_digest ||
              f.key.alias_version !== extension!.alias_version)),
      )
    )
      throw new Error('Semantic identities/pins không khớp.')
    if (
      extension.pairs.some(
        (p) =>
          !frames.has(p.left_id) ||
          !frames.has(p.right_id) ||
          JSON.stringify(p.left_evidence) !==
            JSON.stringify(frames.get(p.left_id)!.evidence) ||
          JSON.stringify(p.right_evidence) !==
            JSON.stringify(frames.get(p.right_id)!.evidence),
      ) ||
      new Set(extension.pairs.map((p) => p.pair_id)).size !==
        extension.pairs.length ||
      extension.timeline.some(
        (t) =>
          !frames.has(t.source_id) ||
          (t.proposed_value && !frames.has(t.target_id!)),
      )
    )
      throw new Error('Semantic references/evidence không khớp.')
  } else if (state === 'NEEDS_REVIEW')
    throw new Error('Semantic extension bị thiếu.')
  return {
    dossierId,
    runId,
    resultDigest:
      row.result_digest === undefined || row.result_digest === null
        ? null
        : hash(row.result_digest),
    state,
    reason: row.reason === null ? null : text(row.reason),
    extension,
    typedTableProjections,
  }
}
export function decodeFindingSemantic(value: unknown): FindingSemantic | null {
  if (value === undefined || value === null) return null
  const row = record(value)
  const result = {
    frame: frame(row.frame),
    pair: row.pair === undefined || row.pair === null ? null : pair(row.pair),
    timeline:
      row.timeline === undefined || row.timeline === null
        ? null
        : timeline(row.timeline),
    profile_digest: hash(row.profile_digest),
    alias_version: integer(row.alias_version),
    alias_digest: row.alias_digest === null ? null : hash(row.alias_digest),
    alignment_key: row.alignment_key === null || row.alignment_key === undefined ? null : array(row.alignment_key, (v) => text(v)),
    conflict_kind: row.conflict_kind === null || row.conflict_kind === undefined ? null : choice(row.conflict_kind, ['SEMANTIC_CONFLICT', 'ARITHMETIC_INCONSISTENCY', 'AMENDMENT_REVIEW', 'COMPARABLE_DIFFERENCE']),
    slots_in_difference: row.slots_in_difference === undefined ? [] : array(row.slots_in_difference, (v) => text(v)),
  }
  if (Boolean(result.pair) === Boolean(result.timeline))
    throw new Error('Finding cần đúng một semantic variant.')
  if (
    result.frame.key.method === 'TENANT_ALIAS' &&
    (result.frame.key.alias_version !== result.alias_version ||
      result.frame.key.alias_digest !== result.alias_digest)
  )
    throw new Error('Finding alias pin không khớp.')
  return result
}
export async function getSemanticResults(
  dossierId: string,
  signal?: AbortSignal,
  expectedRun?: string,
): Promise<SemanticResults> {
  return decodeSemanticResults(
    await getJson<unknown>(
      `/api/v1/dossiers/${encodeURIComponent(dossierId)}/semantic-results`,
      { signal },
    ),
    dossierId,
    expectedRun,
  )
}
export async function fetchSemanticSource(
  source: SemanticEvidence,
): Promise<Blob> {
  if (
    source.citation.validation_status !== 'VALID' ||
    !source.citation.page ||
    source.citation.source_file_id !== source.document_id
  )
    throw new Error('Nguồn chưa được xác minh.')
  const response = await apiFetch(
    `/api/v1/documents/${encodeURIComponent(source.document_id)}/pages/${source.citation.page}/image?variant=preview`,
  )
  if (!response.ok) throw new Error(`Không mở được nguồn (${response.status}).`)
  return response.blob()
}
