export type Ai2ReviewState =
  | 'PASS'
  | 'ANSWERED'
  | 'NEEDS_REVIEW'
  | 'INSUFFICIENT_EVIDENCE'
  | 'BLOCKED'
  | 'NOT_COMPARABLE'

export type CitationStatus = 'LOCATABLE' | 'PARTIAL' | 'UNRESOLVED'
export type CitationScope = 'body' | 'annex' | 'unknown'

export type Bbox = [number, number, number, number]

export type EvidenceCitation = {
  status: CitationStatus
  citationId?: string | null
  documentId?: string | null
  sourceFileId: string | null
  lineId: string | null
  pageNo: number | null
  bbox: Bbox | null
  nodeId: string | null
  scope?: CitationScope
  quote: string
}

export type Ai2SearchHit = {
  text: string
  pageNo: number | null
  sourceFileId: string | null
  lineId: string | null
  bbox: Bbox | null
  citation: EvidenceCitation
}

export type Ai2SearchResult = {
  dossierId: string
  query: string
  answer: string | null
  connected: boolean
  reviewState: Ai2ReviewState
  retrievalLayer: Record<string, unknown>
  reasoningTrace: unknown[]
  usedLlm: boolean
  hits: Ai2SearchHit[]
  contextFindings?: unknown[]
  evidenceIssues?: unknown[]
  coverage?: Record<string, unknown>
  events?: unknown[]
  facts?: unknown[]
  findings?: unknown[]
}

export type Ai2PipelineStep = {
  name: string
  status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'SKIPPED'
  errorCode: string | null
  errorMessage: string | null
}

export type Ai2PipelineStatus = {
  dossierId: string
  runId: string | null
  status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
  errorCode: string | null
  errorMessage: string | null
  steps: Ai2PipelineStep[]
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function asNullableString(value: unknown): string | null {
  const text = asString(value)
  return text || null
}

function asNullableNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function citationScope(value: unknown): CitationScope {
  const normalized = asString(value).toLowerCase()
  if (normalized === 'annex' || normalized === 'phụ lục') return 'annex'
  if (
    normalized === 'body' ||
    normalized === 'contract' ||
    normalized === 'main'
  ) {
    return 'body'
  }
  return 'unknown'
}

function asBbox(value: unknown): Bbox | null {
  if (
    !Array.isArray(value) ||
    value.length !== 4 ||
    !value.every((item) => typeof item === 'number' && Number.isFinite(item))
  ) {
    return null
  }
  return [value[0], value[1], value[2], value[3]]
}

function reviewState(value: unknown): Ai2ReviewState | null {
  const normalized = asString(value).toUpperCase()
  return normalized === 'PASS' ||
    normalized === 'ANSWERED' ||
    normalized === 'NEEDS_REVIEW' ||
    normalized === 'INSUFFICIENT_EVIDENCE' ||
    normalized === 'BLOCKED' ||
    normalized === 'NOT_COMPARABLE'
    ? normalized
    : null
}

function citationFromHit(
  row: Record<string, unknown>,
  text: string,
): EvidenceCitation {
  const nested = asRecord(row.citation) ?? {}
  const sourceFileId =
    asNullableString(row.source_file_id) ??
    asNullableString(nested.source_file_id)
  const lineId =
    asNullableString(row.line_id) ?? asNullableString(nested.line_id)
  const pageNo =
    asNullableNumber(row.page_no) ?? asNullableNumber(nested.page_no)
  const bbox = asBbox(row.bbox) ?? asBbox(nested.bbox)
  const nodeId =
    asNullableString(row.node_id) ?? asNullableString(nested.node_id)
  const quote =
    asString(row.quote) || asString(nested.text_span) || text.slice(0, 200)
  const citationId =
    asNullableString(row.citation_id) ?? asNullableString(nested.citation_id)
  const documentId =
    asNullableString(row.document_id) ??
    asNullableString(nested.document_id) ??
    sourceFileId
  const scope = citationScope(
    row.scope ?? row.document_role ?? nested.scope ?? nested.document_role,
  )
  const status: CitationStatus =
    sourceFileId && lineId
      ? 'LOCATABLE'
      : sourceFileId || pageNo !== null || nodeId
        ? 'PARTIAL'
        : 'UNRESOLVED'

  return {
    status,
    citationId,
    documentId,
    sourceFileId,
    lineId,
    pageNo,
    bbox,
    nodeId,
    scope,
    quote,
  }
}

function normalizeHit(value: unknown): Ai2SearchHit | null {
  const row = asRecord(value)
  if (!row) return null
  const text = asString(row.text) || asString(row.value)
  if (!text) return null
  const citation = citationFromHit(row, text)
  return {
    text,
    pageNo: citation.pageNo,
    sourceFileId: citation.sourceFileId,
    lineId: citation.lineId,
    bbox: citation.bbox,
    citation,
  }
}

export function normalizeAi2SearchResult(
  value: unknown,
  dossierId: string,
): Ai2SearchResult {
  const normalizedDossierId = dossierId.trim()
  if (!normalizedDossierId) throw new Error('dossier scope is required')

  const row = asRecord(value) ?? {}
  const hits = Array.isArray(row.hits)
    ? row.hits
        .map(normalizeHit)
        .filter((hit): hit is Ai2SearchHit => hit !== null)
    : []
  const requestedState = reviewState(row.review_state ?? row.state)
  const hasUnresolvedCitation = hits.some(
    (hit) => hit.citation.status === 'UNRESOLVED',
  )
  const reviewStateValue: Ai2ReviewState = hasUnresolvedCitation
    ? 'NEEDS_REVIEW'
    : (requestedState ?? 'INSUFFICIENT_EVIDENCE')
  const retrievalLayer = asRecord(row.retrieval_layer) ?? {}
  const reasoningTrace = Array.isArray(row.reasoning_trace)
    ? row.reasoning_trace
    : []

  return {
    dossierId: normalizedDossierId,
    query: asString(row.query),
    answer: asNullableString(row.answer),
    connected: row.connected === true,
    reviewState: reviewStateValue,
    retrievalLayer,
    reasoningTrace,
    usedLlm: row.used_llm === true,
    hits,
    contextFindings: Array.isArray(row.context_findings)
      ? row.context_findings
      : [],
    evidenceIssues: Array.isArray(row.evidence_issues)
      ? row.evidence_issues
      : [],
    coverage: asRecord(row.coverage) ?? {},
    events: Array.isArray(row.events) ? row.events : [],
    facts: Array.isArray(row.facts) ? row.facts : [],
    findings: Array.isArray(row.findings) ? row.findings : [],
  }
}
