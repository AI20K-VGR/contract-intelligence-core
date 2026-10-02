import { requestJson } from './client'

export type QueryScope = 'mine' | 'all'

export type QueryHistoryCitation = {
  quote: string
  pageNo: number | null
}

export type QueryHistoryItem = {
  traceId: string
  endpoint: 'ask' | 'query'
  actorId: string
  question: string
  /** null khi AI2 lỗi hoặc câu hỏi có trước khi có lịch sử. */
  answer: string | null
  state: string | null
  citations: QueryHistoryCitation[]
  errorCode: string | null
  createdAt: string
}

export const QUERY_HISTORY_PAGE = 20

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function asText(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function citationOf(value: unknown): QueryHistoryCitation | null {
  const row = asRecord(value)
  if (!row) return null
  const nested = asRecord(row.citation) ?? {}
  const quote =
    asText(row.quote) ||
    asText(nested.text_span) ||
    asText(row.text) ||
    asText(nested.quote)
  const page = row.page_no ?? nested.page_no
  return {
    quote,
    pageNo: typeof page === 'number' && Number.isFinite(page) ? page : null,
  }
}

export function normalizeQueryHistoryItem(
  value: unknown,
): QueryHistoryItem | null {
  const row = asRecord(value)
  if (!row) return null
  const traceId = asText(row.trace_id)
  if (!traceId) return null
  return {
    traceId,
    endpoint: row.endpoint === 'query' ? 'query' : 'ask',
    actorId: asText(row.actor_id),
    question: asText(row.question),
    answer: asText(row.answer) || null,
    state: asText(row.state) || null,
    citations: (Array.isArray(row.citations) ? row.citations : [])
      .map(citationOf)
      .filter((item): item is QueryHistoryCitation => item !== null),
    errorCode: asText(row.error_code) || null,
    createdAt: asText(row.created_at),
  }
}

/**
 * GET /dossiers/{id}/queries. Phân trang bằng limit/offset (không phải
 * page/page_size). `scope=all` chỉ chủ hồ sơ hoặc quản trị xem được (403).
 */
export async function listDossierQueries(
  dossierId: string,
  options: {
    scope?: QueryScope
    limit?: number
    offset?: number
    signal?: AbortSignal
  } = {},
) {
  const params = new URLSearchParams({
    scope: options.scope ?? 'mine',
    limit: String(options.limit ?? QUERY_HISTORY_PAGE),
    offset: String(options.offset ?? 0),
  })
  const { data, meta } = await requestJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/queries?${params}`,
    { signal: options.signal },
  )
  const items = (Array.isArray(data) ? data : [])
    .map(normalizeQueryHistoryItem)
    .filter((item): item is QueryHistoryItem => item !== null)
  return {
    items,
    total: typeof meta?.total === 'number' ? meta.total : items.length,
  }
}
