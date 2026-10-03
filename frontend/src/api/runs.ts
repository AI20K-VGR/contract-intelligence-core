import { ApiError, apiFetch, requestJson } from './client'

export type DossierRun = {
  runId: string
  status: string
}

export type RunSseEvent = {
  id: number | null
  event: string
  data: Record<string, unknown> | null
}

const TERMINAL_RUN_STATUSES = new Set([
  'succeeded',
  'completed',
  'failed',
  'cancelled',
  'dead',
])

export function isTerminalRunStatus(status: string | null | undefined) {
  return Boolean(status && TERMINAL_RUN_STATUSES.has(status))
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

export async function latestDossierRun(
  dossierId: string,
  signal?: AbortSignal,
): Promise<DossierRun | null> {
  const params = new URLSearchParams({
    dossier_id: dossierId,
    limit: '1',
    offset: '0',
  })
  const { data } = await requestJson<unknown>(`/api/v1/runs?${params}`, {
    signal,
  })
  const row = asRecord(Array.isArray(data) ? data[0] : null)
  const runId = typeof row?.run_id === 'string' ? row.run_id : ''
  if (!runId) return null
  return {
    runId,
    status: typeof row.status === 'string' ? row.status : '',
  }
}

export function parseSseBlocks(buffer: string): {
  events: RunSseEvent[]
  rest: string
} {
  const parts = buffer.replace(/\r\n/g, '\n').split('\n\n')
  const rest = parts.pop() ?? ''
  const events: RunSseEvent[] = []
  for (const part of parts) {
    const event = parseSseBlock(part)
    if (event) events.push(event)
  }
  return { events, rest }
}

function parseSseBlock(block: string): RunSseEvent | null {
  let id: number | null = null
  let event = 'message'
  const dataLines: string[] = []
  let hasField = false
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue
    hasField = true
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    const raw = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
    if (field === 'id') {
      const parsed = Number(raw)
      id = Number.isInteger(parsed) && parsed >= 0 ? parsed : null
    } else if (field === 'event') {
      event = raw || 'message'
    } else if (field === 'data') {
      dataLines.push(raw)
    }
  }
  if (!hasField) return null
  let data: Record<string, unknown> | null = null
  if (dataLines.length > 0) {
    try {
      const parsed: unknown = JSON.parse(dataLines.join('\n'))
      data = asRecord(parsed)
    } catch {
      data = null
    }
  }
  return { id, event, data }
}

export async function streamRunEvents(
  runId: string,
  options: {
    signal: AbortSignal
    lastEventId?: number
    onEvent: (event: RunSseEvent) => void
  },
): Promise<void> {
  const lastEventId = options.lastEventId ?? 0
  const params = new URLSearchParams()
  if (lastEventId > 0) params.set('last_event_id', String(lastEventId))
  const query = params.toString()
  const headers = new Headers({ Accept: 'text/event-stream' })
  if (lastEventId > 0) headers.set('Last-Event-ID', String(lastEventId))

  const response = await apiFetch(
    `/api/v1/runs/${encodeURIComponent(runId)}/events${query ? `?${query}` : ''}`,
    { headers, signal: options.signal },
  )
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const record = asRecord(payload)
    const detail = typeof record?.detail === 'string' ? record.detail : ''
    throw new ApiError(response.status, detail || `API ${response.status}`)
  }
  if (!response.body) {
    throw new Error('Máy chủ không mở luồng tiến trình.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) return
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseSseBlocks(buffer)
    buffer = parsed.rest
    for (const event of parsed.events) {
      options.onEvent(event)
      if (event.event === 'run.completed' || event.event === 'error') return
    }
  }
}

export type RunSummary = {
  runId: string
  dossierId: string
  status: string
  triggeredBy: string | null
  durationSeconds: number | null
  createdAt: string | null
  finishedAt: string | null
}

function runSummary(value: unknown): RunSummary | null {
  const row = asRecord(value)
  const runId = typeof row?.run_id === 'string' ? row.run_id : ''
  if (!row || !runId) return null
  const text = (key: string) =>
    typeof row[key] === 'string' && row[key] ? (row[key] as string) : null
  return {
    runId,
    dossierId: typeof row.dossier_id === 'string' ? row.dossier_id : '',
    status: typeof row.status === 'string' ? row.status : '',
    triggeredBy: text('triggered_by'),
    durationSeconds:
      typeof row.duration_seconds === 'number' ? row.duration_seconds : null,
    createdAt: text('created_at'),
    finishedAt: text('finished_at'),
  }
}

/** GET /runs?dossier_id=: lịch sử các lần chạy, mới nhất trước. */
export async function listDossierRuns(
  dossierId: string,
  options: { limit?: number; offset?: number; signal?: AbortSignal } = {},
) {
  const params = new URLSearchParams({
    dossier_id: dossierId,
    limit: String(options.limit ?? 20),
    offset: String(options.offset ?? 0),
  })
  const { data, meta } = await requestJson<unknown>(`/api/v1/runs?${params}`, {
    signal: options.signal,
  })
  const items = (Array.isArray(data) ? data : [])
    .map(runSummary)
    .filter((item): item is RunSummary => item !== null)
  return {
    items,
    total: typeof meta?.total === 'number' ? meta.total : items.length,
  }
}

/** POST /runs/{id}/cancel: chỉ run còn queued/running, 409 nếu đã kết thúc. */
export async function cancelRun(runId: string) {
  const { data } = await requestJson<unknown>(
    `/api/v1/runs/${encodeURIComponent(runId)}/cancel`,
    { method: 'POST', json: {} },
  )
  return runSummary(data)
}

/** POST /dossiers/{id}/reprocess: chạy lại toàn bộ thành một run mới. */
export async function reprocessDossier(dossierId: string) {
  await requestJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/reprocess`,
    { method: 'POST', json: {} },
  )
}

export function runActionErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    if (error.status === 403) return 'Bạn không có quyền thao tác trên hồ sơ này.'
    if (error.status === 404) return 'Không tìm thấy hồ sơ hoặc lần chạy.'
    if (error.status === 409) {
      return error.message || 'Hồ sơ đang có lần chạy khác, hoặc lần chạy đã kết thúc.'
    }
    return error.message
  }
  if (error instanceof TypeError) return 'Không kết nối được backend.'
  return 'Không thực hiện được. Thử lại.'
}

const STATUS_LABELS: Record<string, string> = {
  queued: 'Đang chờ',
  running: 'Đang chạy',
  completed: 'Hoàn thành',
  succeeded: 'Hoàn thành',
  failed: 'Lỗi',
  cancelled: 'Đã hủy',
  dead: 'Dừng hẳn',
}

export function runStatusLabel(status: string) {
  return STATUS_LABELS[status] ?? (status || 'Chưa rõ')
}

export function isCancellableRun(status: string) {
  return status === 'queued' || status === 'running'
}
