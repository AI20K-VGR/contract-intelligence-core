import { apiFetch, getJson } from './client'

export type RunEvent = {
  id: string | null
  event: string
  data: unknown
}

/**
 * Bộ đọc text/event-stream: nhận từng mảnh chữ, gọi `onEvent` cho mỗi sự kiện
 * đủ dòng trống kết thúc. Bỏ qua dòng chú thích (":heartbeat").
 */
export function createSseParser(onEvent: (event: RunEvent) => void) {
  let buffer = ''
  return (chunk: string) => {
    buffer += chunk
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      let id: string | null = null
      let event = 'message'
      const data: string[] = []
      for (const line of block.split(/\r?\n/)) {
        if (!line || line.startsWith(':')) continue
        const colon = line.indexOf(':')
        const field = colon === -1 ? line : line.slice(0, colon)
        const value =
          colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
        if (field === 'id') id = value
        else if (field === 'event') event = value
        else if (field === 'data') data.push(value)
      }
      if (data.length === 0 && event === 'message') continue
      let parsed: unknown = null
      if (data.length > 0) {
        try {
          parsed = JSON.parse(data.join('\n'))
        } catch {
          parsed = data.join('\n')
        }
      }
      onEvent({ id, event, data: parsed })
    }
  }
}

/** Run mới nhất của hồ sơ (BE trả mới nhất trước). */
export async function findLatestRunId(
  dossierId: string,
  signal?: AbortSignal,
): Promise<string | null> {
  const data = await getJson<unknown>(
    `/api/v1/runs?dossier_id=${encodeURIComponent(dossierId)}&limit=1`,
    { signal },
  )
  if (!Array.isArray(data) || data.length === 0) return null
  const first = data[0] as { run_id?: unknown } | null
  return typeof first?.run_id === 'string' ? first.run_id : null
}

export type WatchRunHandlers = {
  /** Mỗi sự kiện server đẩy xuống. */
  onEvent: (event: RunEvent) => void
  /** Mất kết nối: hỏi lại trạng thái một lần rồi nối lại. */
  onLost: () => void
  /** Server từ chối (403/404...): không nối lại. */
  onRejected: (status: number) => void
}

const RETRY_MIN_MS = 1000
const RETRY_MAX_MS = 10000

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve) => {
    const timer = window.setTimeout(resolve, ms)
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer)
        resolve()
      },
      { once: true },
    )
  })
}

/**
 * Nghe tiến độ run qua SSE. Dùng fetch (không phải EventSource) để gửi được
 * Bearer token. Mất kết nối thì báo `onLost` rồi nối lại với Last-Event-ID;
 * hủy `signal` (rời trang) thì ngắt hẳn. Kết thúc khi server gửi run.completed.
 */
export async function watchRun(
  runId: string,
  handlers: WatchRunHandlers,
  signal: AbortSignal,
) {
  let lastId: string | null = null
  let delay = RETRY_MIN_MS
  while (!signal.aborted) {
    let completed = false
    try {
      const headers: Record<string, string> = { Accept: 'text/event-stream' }
      if (lastId) headers['Last-Event-ID'] = lastId
      const response = await apiFetch(
        `/api/v1/runs/${encodeURIComponent(runId)}/events`,
        { headers, signal },
      )
      if (!response.ok) {
        if (response.status >= 400 && response.status < 500) {
          handlers.onRejected(response.status)
          return
        }
        throw new Error(`SSE ${response.status}`)
      }
      if (!response.body) throw new Error('SSE không có body')
      delay = RETRY_MIN_MS
      const reader = response.body
        .pipeThrough(new TextDecoderStream())
        .getReader()
      const parse = createSseParser((event) => {
        if (event.id) lastId = event.id
        if (event.event === 'run.completed') completed = true
        const body = event.data as { error?: unknown } | null
        if (event.event === 'error' && body?.error === 'RUN_NOT_FOUND') {
          completed = true
        }
        handlers.onEvent(event)
      })
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        parse(value)
        if (completed) {
          void reader.cancel()
          break
        }
      }
    } catch {
      if (signal.aborted) return
    }
    if (completed || signal.aborted) return
    handlers.onLost()
    await wait(delay, signal)
    delay = Math.min(delay * 2, RETRY_MAX_MS)
  }
}

export type RunStep = {
  step: string
  status: string
  attempt: number
  pages: number | null
  durationMs: number | null
}

export const RUN_STEP_ORDER = [
  'S0',
  'S1',
  'S2',
  'S3',
  'S4',
  'S5',
  'S6',
  'S7',
  'S8',
  'S9',
  'S10',
] as const

export const RUN_STEP_LABELS: Record<string, string> = {
  S0: 'Kiểm tra tệp tải lên',
  S1: 'Kiểm tra PDF và số trang',
  S2: 'Dựng ảnh từng trang',
  S3: 'Phân loại trang (chữ sẵn có / scan)',
  S4: 'Nhận diện chữ, bố cục, bảng',
  S5: 'Kiểm tra chất lượng kết quả',
  S6: 'Dựng cấu trúc điều khoản, bảng',
  S7: 'Trích xuất dữ kiện và trích dẫn',
  S8: 'Liên kết phụ lục',
  S9: 'So sánh, tìm mâu thuẫn',
  S10: 'Xếp hàng rà soát và chốt kết quả',
}

/** Đọc payload `step.changed` do BE đẩy xuống; null nếu thiếu mã bước. */
export function stepFromEvent(event: RunEvent): RunStep | null {
  if (event.event !== 'step.changed') return null
  const data = event.data as Record<string, unknown> | null
  if (!data || typeof data.step !== 'string') return null
  return {
    step: data.step,
    status: typeof data.status === 'string' ? data.status : 'queued',
    attempt: typeof data.attempt === 'number' ? data.attempt : 1,
    pages: typeof data.pages === 'number' ? data.pages : null,
    durationMs: typeof data.duration_ms === 'number' ? data.duration_ms : null,
  }
}

/** Trạng thái các bước đang lưu trong DB (dùng khi mở trang sau khi run đã chạy). */
export async function listRunSteps(
  runId: string,
  signal?: AbortSignal,
): Promise<RunStep[]> {
  const data = await getJson<unknown>(
    `/api/v1/runs/${encodeURIComponent(runId)}/steps`,
    { signal },
  )
  if (!Array.isArray(data)) return []
  return data.flatMap((item): RunStep[] => {
    const row = item as Record<string, unknown> | null
    if (!row || typeof row.step !== 'string') return []
    return [
      {
        step: row.step,
        status: typeof row.status === 'string' ? row.status : 'queued',
        attempt: typeof row.attempt === 'number' ? row.attempt : 1,
        pages: typeof row.pages === 'number' ? row.pages : null,
        durationMs:
          typeof row.duration_ms === 'number' ? row.duration_ms : null,
      },
    ]
  })
}
