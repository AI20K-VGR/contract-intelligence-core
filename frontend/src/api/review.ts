import { ApiError, getJson, requestJson, type ApiMeta } from './client'

export type ReviewActionType =
  'confirm' | 'correct' | 'reject' | 'needs_more_evidence'

export type ReviewItem = {
  id: string
  dossierId: string
  runId: string
  targetType: string
  targetId: string
  reason: string
  priority: string
  status: string
  version: number
  sourceTraceId: string | null
  sourceObservationId: string | null
  targetSnapshot: Record<string, unknown> | null
  createdAt: string | null
}

export type ReviewRevision = {
  revisionNumber: number
  action: string
  authorUserId: string
  authorRole: string | null
  comment: string | null
  correctedValue: unknown
  correctedBbox: unknown
  previousVersion: number | null
  createdAt: string | null
}

export type ReviewActionInput = {
  baseVersion: number
  action: ReviewActionType
  correctedValue?: Record<string, unknown> | null
  correctedBbox?: unknown[] | null
  comment?: string | null
}

export type ReviewActionResult = {
  reviewActionId: string
  itemStatus: string
  newVersion: number
  effectiveValue: unknown
  machineValue: unknown
  jobStatus: string | null
  openItemsRemaining: number | null
  idempotentReplay: boolean
}

export type ReviewDossierState = {
  id: string
  name: string
  openReviewItems: number
  pendingConflicts: number
  latestJobStatus: string | null
  raw: Record<string, unknown>
}

export type ReviewQueue = {
  items: ReviewItem[]
  meta?: ApiMeta
}

export class ReviewConflictError extends Error {
  readonly currentState: Record<string, unknown> | null
  readonly submittedAction: Record<string, unknown> | null

  constructor(
    message: string,
    currentState: Record<string, unknown> | null,
    submittedAction: Record<string, unknown> | null,
  ) {
    super(message)
    this.name = 'ReviewConflictError'
    this.currentState = currentState
    this.submittedAction = submittedAction
  }
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

export function normalizeReviewItem(value: unknown): ReviewItem {
  const row = asRecord(value)
  const id = asString(row?.id)
  if (!row || !id) throw new Error('Review item thiếu id.')
  const snapshot = asRecord(row.target_snapshot)
  return {
    id,
    dossierId: asString(row.dossier_id),
    runId: asString(row.run_id),
    targetType: asString(row.target_type),
    targetId: asString(row.target_id),
    reason: asString(row.reason),
    priority: asString(row.priority, 'P3'),
    status: asString(row.status, 'open'),
    version: asNumber(row.version, 1),
    sourceTraceId: asNullableString(row.source_trace_id),
    sourceObservationId: asNullableString(row.source_observation_id),
    targetSnapshot: snapshot,
    createdAt: asNullableString(row.created_at),
  }
}

export function normalizeReviewRevision(value: unknown): ReviewRevision {
  const row = asRecord(value)
  if (!row) throw new Error('Review revision không hợp lệ.')
  return {
    revisionNumber: asNumber(row.revision_number),
    action: asString(row.action),
    authorUserId: asString(row.author_user_id),
    authorRole: asNullableString(row.author_role),
    comment: asNullableString(row.comment),
    correctedValue: row.corrected_value ?? null,
    correctedBbox: row.corrected_bbox ?? null,
    previousVersion:
      typeof row.previous_version === 'number' ? row.previous_version : null,
    createdAt: asNullableString(row.created_at),
  }
}

function normalizeList(value: unknown): ReviewItem[] {
  if (!Array.isArray(value))
    throw new Error('Backend trả về review queue không hợp lệ.')
  return value.map(normalizeReviewItem)
}

function normalizeDossierState(value: unknown): ReviewDossierState {
  const row = asRecord(value)
  const id = asString(row?.id)
  if (!row || !id)
    throw new Error('Backend trả về trạng thái dossier không hợp lệ.')
  return {
    id,
    name: asString(row.name),
    openReviewItems: asNumber(row.open_review_items),
    pendingConflicts: asNumber(row.pending_conflicts),
    latestJobStatus: asNullableString(row.latest_job_status),
    raw: row,
  }
}

export async function listReviewItems(
  dossierId: string,
  signal?: AbortSignal,
): Promise<ReviewQueue> {
  if (!dossierId)
    throw new Error('Dossier scope là bắt buộc để tải review queue.')
  const result = await requestJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/review-items?limit=100`,
    { signal },
  )
  return { items: normalizeList(result.data), meta: result.meta }
}

export async function getReviewItem(itemId: string, signal?: AbortSignal) {
  const value = await getJson<unknown>(
    `/api/v1/review-items/${encodeURIComponent(itemId)}`,
    { signal },
  )
  return normalizeReviewItem(value)
}

export async function listReviewRevisions(
  itemId: string,
  signal?: AbortSignal,
) {
  const value = await getJson<unknown>(
    `/api/v1/review-items/${encodeURIComponent(itemId)}/revisions`,
    { signal },
  )
  if (!Array.isArray(value))
    throw new Error('Backend trả về revision không hợp lệ.')
  return value.map(normalizeReviewRevision)
}

export async function submitReviewAction(
  itemId: string,
  input: ReviewActionInput,
): Promise<ReviewActionResult> {
  try {
    const result = await requestJson<unknown>(
      `/api/v1/review-items/${encodeURIComponent(itemId)}/actions`,
      {
        method: 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        json: {
          action: input.action,
          base_version: input.baseVersion,
          corrected_value: input.correctedValue ?? null,
          corrected_bbox: input.correctedBbox ?? null,
          comment: input.comment ?? null,
        },
      },
    )
    const row = asRecord(result.data)
    if (!row) throw new Error('Backend trả về review action không hợp lệ.')
    return {
      reviewActionId: asString(row.review_action_id),
      itemStatus: asString(row.item_status),
      newVersion: asNumber(row.new_version),
      effectiveValue: row.effective_value ?? null,
      machineValue: row.machine_value ?? null,
      jobStatus: asNullableString(row.job_status),
      openItemsRemaining:
        typeof row.open_items_remaining === 'number'
          ? row.open_items_remaining
          : null,
      idempotentReplay: row.idempotent_replay === true,
    }
  } catch (cause: unknown) {
    if (cause instanceof ApiError && cause.status === 409) {
      const body = asRecord(cause.details)
      throw new ReviewConflictError(
        cause.message,
        asRecord(body?.current_state),
        asRecord(body?.your_submitted_action),
      )
    }
    throw cause
  }
}

export async function lockDossier(dossierId: string) {
  const value = await getJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/lock`,
    { method: 'POST' },
  )
  return normalizeDossierState(value)
}

export async function approveDossier(dossierId: string, comment?: string) {
  const value = await requestJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/approve`,
    {
      method: 'POST',
      json: comment?.trim() ? { comment: comment.trim() } : {},
    },
  )
  return normalizeDossierState(value.data)
}
