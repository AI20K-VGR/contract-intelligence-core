import { getJson } from './client'

export type ContractGraphKind = 'operation' | 'pair'
export type ContractGraphStatus =
  | 'READY'
  | 'PENDING'
  | 'STALE'
  | 'UNAVAILABLE'
  | 'PERSISTENCE_UNKNOWN'
  | 'PERSIST_FAILED'
  | 'SKIPPED'
  | 'FAILED'

export type ContractGraphEdge = {
  id: string
  kind: 'OPERATION' | 'PAIR'
  label: string
  directed: boolean
  source_node_id: string
  target_node_id: string
  source_document_id: string | null
  target_document_id: string | null
  target_address?: string | null
  review_state: string
  source_citation_ref: string
  target_citation_ref: string
  digest: string
}

export type ContractGraphPage = {
  job_id: string
  snapshot_digest: string
  graph_kind: ContractGraphKind
  status: ContractGraphStatus
  edges: ContractGraphEdge[]
  total_count: number
  has_more: boolean
  next_cursor: string | null
}

export type ProcessingTraceStatus =
  | 'COMPLETE'
  | 'IN_PROGRESS'
  | 'INTERRUPTED_UNKNOWN'
  | 'INCOMPLETE_UNKNOWN'
  | 'TRACE_UNAVAILABLE'

export type ProcessingTraceStage = {
  stage_id: string
  status:
    | 'RUNNING'
    | 'COMPLETED'
    | 'FAILED'
    | 'SKIPPED'
    | 'INTERRUPTED_UNKNOWN'
    | 'INCOMPLETE_UNKNOWN'
  started_ms: number | null
  duration_ms: number | null
  item_count: number | null
  reason_code: string | null
}

export type ProcessingTrace = {
  job_id: string
  snapshot_digest: string
  status: ProcessingTraceStatus
  trace_status: 'AVAILABLE' | 'UNAVAILABLE'
  job_status?: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
  stages: ProcessingTraceStage[]
}

const GRAPH_STATUSES = new Set<ContractGraphStatus>([
  'READY',
  'PENDING',
  'STALE',
  'UNAVAILABLE',
  'PERSISTENCE_UNKNOWN',
  'PERSIST_FAILED',
  'SKIPPED',
  'FAILED',
])
const TRACE_STATUSES = new Set<ProcessingTraceStatus>([
  'COMPLETE',
  'IN_PROGRESS',
  'INTERRUPTED_UNKNOWN',
  'INCOMPLETE_UNKNOWN',
  'TRACE_UNAVAILABLE',
])
const JOB_STATUSES = new Set([
  'QUEUED',
  'RUNNING',
  'SUCCEEDED',
  'FAILED',
  'CANCELLED',
])
const STAGE_STATUSES = new Set<ProcessingTraceStage['status']>([
  'RUNNING',
  'COMPLETED',
  'FAILED',
  'SKIPPED',
  'INTERRUPTED_UNKNOWN',
  'INCOMPLETE_UNKNOWN',
])

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('AI2 graph response must be an object')
  }
  return value as Record<string, unknown>
}

function assertKeys(value: Record<string, unknown>, keys: string[]) {
  if (Object.keys(value).some((key) => !keys.includes(key))) {
    throw new TypeError('AI2 graph response contains unsupported fields')
  }
}

function stringField(value: unknown, name: string): string {
  if (typeof value !== 'string' || !value) {
    throw new TypeError(`AI2 graph response has invalid ${name}`)
  }
  return value
}

function validateGraphPage(
  raw: unknown,
  expected: {
    jobId: string
    snapshotDigest: string
    graphKind: ContractGraphKind
  },
): ContractGraphPage {
  const value = record(raw)
  assertKeys(value, [
    'job_id',
    'snapshot_digest',
    'graph_kind',
    'status',
    'edges',
    'total_count',
    'has_more',
    'next_cursor',
  ])
  if (
    value.job_id !== expected.jobId ||
    value.snapshot_digest !== expected.snapshotDigest ||
    value.graph_kind !== expected.graphKind ||
    typeof value.status !== 'string' ||
    !GRAPH_STATUSES.has(value.status as ContractGraphStatus)
  ) {
    throw new TypeError('AI2 graph page identity or status mismatch')
  }
  if (
    !Array.isArray(value.edges) ||
    typeof value.total_count !== 'number' ||
    !Number.isInteger(value.total_count) ||
    value.total_count < 0 ||
    typeof value.has_more !== 'boolean' ||
    (value.next_cursor !== null && typeof value.next_cursor !== 'string') ||
    (value.has_more && !value.next_cursor)
  ) {
    throw new TypeError('AI2 graph page shape is invalid')
  }
  const edges = value.edges.map((item): ContractGraphEdge => {
    const edge = record(item)
    assertKeys(edge, [
      'id',
      'kind',
      'label',
      'directed',
      'source_node_id',
      'target_node_id',
      'source_document_id',
      'target_document_id',
      'target_address',
      'review_state',
      'source_citation_ref',
      'target_citation_ref',
      'digest',
    ])
    const kind = expected.graphKind === 'pair' ? 'PAIR' : 'OPERATION'
    if (
      edge.kind !== kind ||
      typeof edge.directed !== 'boolean' ||
      (typeof edge.target_address !== 'undefined' &&
        edge.target_address !== null &&
        typeof edge.target_address !== 'string')
    ) {
      throw new TypeError('AI2 graph edge shape is invalid')
    }
    return {
      id: stringField(edge.id, 'edge id'),
      kind,
      label: stringField(edge.label, 'edge label'),
      directed: edge.directed,
      source_node_id: stringField(edge.source_node_id, 'source node'),
      target_node_id: stringField(edge.target_node_id, 'target node'),
      source_document_id: nullableStringField(
        edge.source_document_id,
        'source document',
      ),
      target_document_id: nullableStringField(
        edge.target_document_id,
        'target document',
      ),
      ...(typeof edge.target_address === 'undefined'
        ? {}
        : { target_address: edge.target_address as string | null }),
      review_state: stringField(edge.review_state, 'review state'),
      source_citation_ref: stringField(
        edge.source_citation_ref,
        'source citation ref',
      ),
      target_citation_ref: stringField(
        edge.target_citation_ref,
        'target citation ref',
      ),
      digest: stringField(edge.digest, 'edge digest'),
    }
  })
  if (value.status !== 'READY' && edges.length > 0) {
    throw new TypeError('AI2 graph page returned edges for a non-ready status')
  }
  return {
    job_id: expected.jobId,
    snapshot_digest: expected.snapshotDigest,
    graph_kind: expected.graphKind,
    status: value.status as ContractGraphStatus,
    edges,
    total_count: value.total_count,
    has_more: value.has_more,
    next_cursor: value.next_cursor as string | null,
  }
}

function nullableStringField(value: unknown, name: string): string | null {
  if (value !== null && (typeof value !== 'string' || !value)) {
    throw new TypeError(`AI2 graph response has invalid ${name}`)
  }
  return value as string | null
}

function validateTrace(
  raw: unknown,
  jobId: string,
  snapshotDigest: string,
): ProcessingTrace {
  const value = record(raw)
  assertKeys(value, [
    'job_id',
    'schema_version',
    'snapshot_digest',
    'status',
    'trace_status',
    'stages',
    'execution_id',
    'job_status',
    'reason_code',
  ])
  for (const field of ['execution_id', 'job_status', 'reason_code']) {
    if (
      typeof value[field] !== 'undefined' &&
      typeof value[field] !== 'string'
    ) {
      throw new TypeError(`AI2 trace ${field} is invalid`)
    }
  }
  if (
    typeof value.job_status === 'string' &&
    !JOB_STATUSES.has(value.job_status)
  ) {
    throw new TypeError('AI2 trace job status is invalid')
  }
  if (
    value.job_id !== jobId ||
    value.snapshot_digest !== snapshotDigest ||
    value.schema_version !== 'ai2.processing-trace.v1' ||
    typeof value.status !== 'string' ||
    !TRACE_STATUSES.has(value.status as ProcessingTraceStatus) ||
    (value.trace_status !== 'AVAILABLE' &&
      value.trace_status !== 'UNAVAILABLE') ||
    !Array.isArray(value.stages)
  ) {
    throw new TypeError('AI2 trace identity or status mismatch')
  }
  const stages = value.stages.map((item): ProcessingTraceStage => {
    const stage = record(item)
    assertKeys(stage, [
      'stage_id',
      'status',
      'started_ms',
      'duration_ms',
      'item_count',
      'reason_code',
    ])
    if (
      typeof stage.status !== 'string' ||
      !STAGE_STATUSES.has(stage.status as ProcessingTraceStage['status'])
    ) {
      throw new TypeError('AI2 trace stage status is invalid')
    }
    const optionalCount = (item: unknown) =>
      item === null ||
      (typeof item === 'number' && Number.isInteger(item) && item >= 0)
    if (
      ![stage.started_ms, stage.duration_ms, stage.item_count].every(
        optionalCount,
      )
    ) {
      throw new TypeError('AI2 trace stage timing is invalid')
    }
    if (stage.reason_code !== null && typeof stage.reason_code !== 'string') {
      throw new TypeError('AI2 trace stage reason is invalid')
    }
    return {
      stage_id: stringField(stage.stage_id, 'stage id'),
      status: stage.status as ProcessingTraceStage['status'],
      started_ms: stage.started_ms as number | null,
      duration_ms: stage.duration_ms as number | null,
      item_count: stage.item_count as number | null,
      reason_code: stage.reason_code as string | null,
    }
  })
  return {
    job_id: jobId,
    snapshot_digest: snapshotDigest,
    status: value.status as ProcessingTraceStatus,
    trace_status: value.trace_status,
    ...(typeof value.job_status === 'string'
      ? { job_status: value.job_status as ProcessingTrace['job_status'] }
      : {}),
    stages,
  }
}

export async function getContractGraphPage(input: {
  dossierId: string
  jobId: string
  snapshotDigest: string
  graphKind: ContractGraphKind
  cursor?: string | null
  limit?: number
  signal?: AbortSignal
}): Promise<ContractGraphPage> {
  const params = new URLSearchParams({
    job_id: input.jobId,
    snapshot_digest: input.snapshotDigest,
  })
  if (input.cursor) params.set('cursor', input.cursor)
  if (input.limit !== undefined) params.set('limit', String(input.limit))
  const raw = await getJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(input.dossierId)}/ai2/contract-graph/${input.graphKind}?${params}`,
    { signal: input.signal },
  )
  return validateGraphPage(raw, input)
}

export async function getProcessingTrace(input: {
  dossierId: string
  jobId: string
  snapshotDigest: string
  signal?: AbortSignal
}): Promise<ProcessingTrace> {
  const params = new URLSearchParams({
    job_id: input.jobId,
    snapshot_digest: input.snapshotDigest,
  })
  const raw = await getJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(input.dossierId)}/ai2/processing-trace?${params}`,
    { signal: input.signal },
  )
  return validateTrace(raw, input.jobId, input.snapshotDigest)
}
