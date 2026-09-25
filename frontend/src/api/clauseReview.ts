import { ApiError, getJson, requestJson } from './client'
import type { ClauseNode } from './structure'

export type ClauseReviewAction = 'confirm' | 'reject' | 'correct'

export type ClauseReviewEntry = {
  revisionNumber: number
  action: string
  comment: string | null
  assessment: string | null
  reviewerId: string
  reviewerName: string | null
  reviewerEmail: string | null
  createdAt: string | null
}

export type ClauseStaleReview = {
  textChanged: boolean
  reviewedText: string | null
  latest: ClauseReviewEntry
  history: ClauseReviewEntry[]
}

export type ClauseReview = {
  nodeId: string
  reviewItemId: string | null
  version: number
  status: string
  dossierLocked: boolean
  latest: ClauseReviewEntry | null
  history: ClauseReviewEntry[]
  stale: ClauseStaleReview | null
}

export class ClauseReviewConflictError extends Error {
  readonly current: ClauseReview | null

  constructor(message: string, current: ClauseReview | null) {
    super(message)
    this.name = 'ClauseReviewConflictError'
    this.current = current
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function asText(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function normalizeEntry(value: unknown): ClauseReviewEntry {
  const row = asRecord(value) ?? {}
  const corrected = asRecord(row.corrected_value)
  return {
    revisionNumber: typeof row.revision_number === 'number' ? row.revision_number : 0,
    action: asText(row.action) ?? '',
    comment: asText(row.comment),
    assessment: asText(corrected?.assessment),
    reviewerId: asText(row.reviewer_id) ?? '',
    reviewerName: asText(row.reviewer_name),
    reviewerEmail: asText(row.reviewer_email),
    createdAt: asText(row.created_at),
  }
}

function normalizeStale(value: unknown): ClauseStaleReview | null {
  const row = asRecord(value)
  if (!row?.latest) return null
  return {
    textChanged: row.text_changed === true,
    reviewedText: asText(row.reviewed_text),
    latest: normalizeEntry(row.latest),
    history: Array.isArray(row.history) ? row.history.map(normalizeEntry) : [],
  }
}

function normalizeReview(value: unknown): ClauseReview {
  const row = asRecord(value)
  if (!row || typeof row.node_id !== 'string')
    throw new Error('Backend trả về thẩm định không hợp lệ.')
  return {
    stale: normalizeStale(row.stale),
    nodeId: row.node_id,
    reviewItemId: asText(row.review_item_id),
    version: typeof row.version === 'number' ? row.version : 0,
    status: asText(row.status) ?? 'unreviewed',
    dossierLocked: row.dossier_locked === true,
    latest: row.latest ? normalizeEntry(row.latest) : null,
    history: Array.isArray(row.history) ? row.history.map(normalizeEntry) : [],
  }
}

/**
 * Nút cây dựng trên trình duyệt từ dòng OCR không có trong DB. Backend neo vào
 * dòng OCR mở nút và dùng mô tả này để tìm thẩm định của lần phân tích trước.
 */
export type ClauseReviewTarget = {
  documentId: string
  node: ClauseNode
  ordinal: number
}

function reviewPath(target: ClauseReviewTarget, query: URLSearchParams) {
  query.set('document_id', target.documentId)
  return `/api/v1/clause-nodes/${encodeURIComponent(target.node.id)}/review?${query}`
}

function descriptor(target: ClauseReviewTarget) {
  return {
    node_type: target.node.nodeType,
    number: target.node.number ?? '',
    label: target.node.label,
    ordinal: target.ordinal,
    text: target.node.text,
  }
}

async function sha256Hex(value: string) {
  const bytes = new TextEncoder().encode(value)
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, '0'),
  ).join('')
}

/** Thứ tự của nút trong các nút trùng loại/số/nhãn, theo thứ tự đọc của cây. */
export function clauseOrdinal(nodes: ClauseNode[], id: string) {
  const counts = new Map<string, number>()
  let found = 0
  const walk = (list: ClauseNode[]): boolean => {
    for (const node of list) {
      const key = `${node.nodeType}\u0000${node.number ?? ''}\u0000${node.label}`
      const seen = counts.get(key) ?? 0
      if (node.id === id) {
        found = seen
        return true
      }
      counts.set(key, seen + 1)
      if (walk(node.children)) return true
    }
    return false
  }
  walk(nodes)
  return found
}

export async function getClauseReview(
  target: ClauseReviewTarget,
  signal?: AbortSignal,
) {
  const { text, ...rest } = descriptor(target)
  const query = new URLSearchParams({
    ...rest,
    ordinal: String(rest.ordinal),
    text_sha256: await sha256Hex(text),
  })
  const value = await getJson<unknown>(reviewPath(target, query), { signal })
  return normalizeReview(value)
}

export async function saveClauseReview(
  target: ClauseReviewTarget,
  input: { action: ClauseReviewAction; baseVersion: number; comment: string },
) {
  try {
    const result = await requestJson<unknown>(
      reviewPath(target, new URLSearchParams()),
      {
        method: 'POST',
        json: {
          action: input.action,
          base_version: input.baseVersion,
          comment: input.comment.trim() || null,
          node: descriptor(target),
        },
      },
    )
    return normalizeReview(result.data)
  } catch (cause: unknown) {
    if (cause instanceof ApiError && cause.status === 409) {
      const state = asRecord(cause.details)?.current_state
      throw new ClauseReviewConflictError(
        cause.message,
        state ? normalizeReview(state) : null,
      )
    }
    throw cause
  }
}
