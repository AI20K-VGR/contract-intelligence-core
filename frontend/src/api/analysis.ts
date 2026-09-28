import { getJson } from './client'

export type EvidenceStatus = 'LOCATABLE' | 'PARTIAL' | 'UNRESOLVED'

export type StructuredEvidence = {
  status: EvidenceStatus
  citationId: string | null
  sourceFileId: string | null
  lineId: string | null
  pageNo: number | null
  bbox: [number, number, number, number] | null
  quote: string
}

export type DossierFact = {
  id: string
  key: string
  factType: string
  rawText: string
  machineValue: unknown
  effectiveValue: unknown
  reviewState: string
  confidence: number
  currentVersion: number
  evidence: StructuredEvidence
}

export type FindingSide = {
  side: string
  documentId: string
  documentRole: string | null
  valueSnapshot: unknown
  evidence: StructuredEvidence
}

export type DossierFinding = {
  id: string
  findingType: string
  scope: string
  topic: string
  disposition: string
  severity: string
  confidence: number
  rationale: string
  disclaimer: string
  sides: FindingSide[]
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function asString(value: unknown, fallback = '') {
  return typeof value === 'string' ? value : fallback
}

function asNumber(value: unknown, fallback = 0) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function asNullableString(value: unknown) {
  return typeof value === 'string' ? value : null
}

function asBBox(value: unknown): [number, number, number, number] | null {
  if (!Array.isArray(value) || value.length < 4) return null
  const bbox = value.slice(0, 4).map(Number)
  if (bbox.some((item) => !Number.isFinite(item))) return null
  return [bbox[0], bbox[1], bbox[2], bbox[3]]
}

function citationEvidence(
  value: unknown,
  fallbackDocumentId?: string,
): StructuredEvidence {
  const row = asRecord(value)
  const segments = Array.isArray(row?.segments) ? row.segments : []
  const segment = asRecord(segments[0])
  const sourceFileId =
    asNullableString(row?.source_file_id) ??
    asNullableString(row?.document_id) ??
    asNullableString(segment?.source_file_id) ??
    fallbackDocumentId ??
    null
  const lineId =
    asNullableString(row?.line_id) ?? asNullableString(segment?.line_id)
  const pageValue =
    row?.page_no ?? row?.page_number ?? segment?.page_no ?? segment?.page_number
  const pageNo =
    typeof pageValue === 'number' && pageValue > 0 ? pageValue : null
  const bbox = asBBox(row?.bbox ?? segment?.bbox)
  const citationId =
    asNullableString(row?.id) ?? asNullableString(row?.citation_id)
  const quote = asString(row?.quote) || asString(row?.text_span)
  const locatable = Boolean(sourceFileId && pageNo && (lineId || bbox))
  return {
    status: locatable
      ? 'LOCATABLE'
      : citationId || quote
        ? 'PARTIAL'
        : 'UNRESOLVED',
    citationId,
    sourceFileId,
    lineId,
    pageNo,
    bbox,
    quote,
  }
}

export function normalizeFact(value: unknown): DossierFact {
  const row = asRecord(value)
  const fact = asRecord(row?.fact)
  const id = asString(fact?.id)
  if (!fact || !id) throw new Error('Fact không hợp lệ.')
  return {
    id,
    key: asString(fact.key),
    factType: asString(fact.fact_type),
    rawText: asString(fact.raw_text),
    machineValue: row?.machine_value ?? fact.normalized_value ?? null,
    effectiveValue:
      row?.effective_value ??
      row?.machine_value ??
      fact.normalized_value ??
      null,
    reviewState: asString(row?.review_state, 'unreviewed'),
    confidence: asNumber(fact.confidence),
    currentVersion: asNumber(row?.current_version),
    evidence: citationEvidence(
      fact.citation,
      asString(fact.document_id) || undefined,
    ),
  }
}

export function normalizeFinding(value: unknown): DossierFinding {
  const row = asRecord(value)
  const id = asString(row?.id)
  if (!row || !id) throw new Error('Finding không hợp lệ.')
  const sides = Array.isArray(row.sides)
    ? row.sides.flatMap((value): FindingSide[] => {
        const side = asRecord(value)
        if (!side) return []
        return [
          {
            side: asString(side.side),
            documentId: asString(side.document_id),
            documentRole: asNullableString(side.document_role),
            valueSnapshot: side.value_snapshot ?? null,
            evidence: citationEvidence(
              side.citation,
              asString(side.document_id) || undefined,
            ),
          },
        ]
      })
    : []
  return {
    id,
    findingType: asString(row.finding_type),
    scope: asString(row.scope, 'unknown'),
    topic: asString(row.key_or_topic, 'Nội dung cần kiểm tra'),
    disposition: asString(row.disposition),
    severity: asString(row.severity),
    confidence: asNumber(row.confidence),
    rationale: asString(row.rationale),
    disclaimer: asString(row.disclaimer),
    sides,
  }
}

export async function listDossierFacts(
  dossierId: string,
  signal?: AbortSignal,
) {
  const data = await getJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/facts?effective=true`,
    { signal },
  )
  if (!Array.isArray(data))
    throw new Error('Backend trả về facts không hợp lệ.')
  return data.map(normalizeFact)
}

export async function listDossierFindings(
  dossierId: string,
  signal?: AbortSignal,
) {
  const data = await getJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/findings?limit=100&offset=0`,
    { signal },
  )
  if (!Array.isArray(data))
    throw new Error('Backend trả về findings không hợp lệ.')
  return data.map(normalizeFinding)
}
