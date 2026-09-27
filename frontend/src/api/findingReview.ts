import { ApiError, getJson, requestJson } from './client'

export type FindingReviewAction = 'confirm' | 'reject' | 'correct'

export type FindingReviewEntry = {
  revisionNumber: number
  action: string
  comment: string | null
  assessment: string | null
  reviewerId: string
  reviewerName: string | null
  reviewerEmail: string | null
  createdAt: string | null
}

export type FindingStaleReview = {
  textChanged: boolean
  reviewedText: string | null
  latest: FindingReviewEntry
  history: FindingReviewEntry[]
}

export type FindingReview = {
  findingId: string
  reviewItemId: string | null
  version: number
  status: string
  dossierLocked: boolean
  latest: FindingReviewEntry | null
  history: FindingReviewEntry[]
  stale: FindingStaleReview | null
}

export class FindingReviewConflictError extends Error {
  readonly current: FindingReview | null

  constructor(message: string, current: FindingReview | null) {
    super(message)
    this.name = 'FindingReviewConflictError'
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

function normalizeEntry(value: unknown): FindingReviewEntry {
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

function normalizeStale(value: unknown): FindingStaleReview | null {
  const row = asRecord(value)
  if (!row?.latest) return null
  return {
    textChanged: row.text_changed === true,
    reviewedText: asText(row.reviewed_text),
    latest: normalizeEntry(row.latest),
    history: Array.isArray(row.history) ? row.history.map(normalizeEntry) : [],
  }
}

function normalizeReview(value: unknown): FindingReview {
  const row = asRecord(value)
  if (!row || typeof row.finding_id !== 'string')
    throw new Error('Backend trả về thẩm định không hợp lệ.')
  return {
    findingId: row.finding_id,
    reviewItemId: asText(row.review_item_id),
    version: typeof row.version === 'number' ? row.version : 0,
    status: asText(row.status) ?? 'unreviewed',
    dossierLocked: row.dossier_locked === true,
    latest: row.latest ? normalizeEntry(row.latest) : null,
    history: Array.isArray(row.history) ? row.history.map(normalizeEntry) : [],
    stale: normalizeStale(row.stale),
  }
}

function reviewPath(findingId: string) {
  return `/api/v1/findings/${encodeURIComponent(findingId)}/review`
}

export async function getFindingReview(findingId: string, signal?: AbortSignal) {
  const value = await getJson<unknown>(reviewPath(findingId), { signal })
  return normalizeReview(value)
}

export async function saveFindingReview(
  findingId: string,
  input: { action: FindingReviewAction; baseVersion: number; comment: string },
) {
  try {
    const result = await requestJson<unknown>(reviewPath(findingId), {
      method: 'POST',
      json: {
        action: input.action,
        base_version: input.baseVersion,
        comment: input.comment.trim() || null,
      },
    })
    return normalizeReview(result.data)
  } catch (cause: unknown) {
    if (cause instanceof ApiError && cause.status === 409) {
      const state = asRecord(cause.details)?.current_state
      throw new FindingReviewConflictError(
        cause.message,
        state ? normalizeReview(state) : null,
      )
    }
    throw cause
  }
}
