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

export type StepProgressUnit = 'page' | 'document' | 'chunk' | 'clause' | 'pair'

/** Tiến độ trong một bước (DOC-05b v3.2.0), ví dụ 37/202 trang. */
export type StepProgress = {
  done: number
  total: number
  unit: StepProgressUnit
}

const STEP_PROGRESS_UNITS: Record<StepProgressUnit, string> = {
  page: 'trang',
  document: 'tài liệu',
  chunk: 'đoạn',
  clause: 'điều khoản',
  pair: 'cặp',
}

export type RunStep = {
  step: string
  status: string
  attempt: number
  pages: number | null
  durationMs: number | null
  /** null: BE không đo được tiến độ bước này, giao diện hiện vòng quay. */
  progress: StepProgress | null
}

/** Đọc `progress` của một bước; thiếu, sai kiểu hay `unit` lạ đều coi như null. */
export function parseStepProgress(raw: unknown): StepProgress | null {
  if (!raw || typeof raw !== 'object') return null
  const { done, total, unit } = raw as Record<string, unknown>
  if (
    !Number.isInteger(done) ||
    !Number.isInteger(total) ||
    (total as number) < 1 ||
    typeof unit !== 'string' ||
    !Object.hasOwn(STEP_PROGRESS_UNITS, unit)
  ) {
    return null
  }
  const count = total as number
  return {
    done: Math.min(Math.max(done as number, 0), count),
    total: count,
    unit: unit as StepProgressUnit,
  }
}

/** "37/202 trang" */
export function formatStepProgress(progress: StepProgress) {
  return `${progress.done}/${progress.total} ${STEP_PROGRESS_UNITS[progress.unit]}`
}

/** Phần trăm đã xong của bước, làm tròn xuống để chưa xong thì chưa tới 100. */
export function stepProgressPercent(progress: StepProgress) {
  return Math.floor((progress.done / progress.total) * 100)
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

// Theo việc BE ghi vào từng bước (DOC-05b v3.2.0, "Tiến độ trong bước"): S2 là
// cả lượt OCR của AI1 (chữ, bố cục, bảng), S4 là lúc AI2 bắt đầu xử lý hồ sơ.
export const RUN_STEP_LABELS: Record<string, string> = {
  S0: 'Kiểm tra tệp tải lên',
  S1: 'Kiểm tra PDF và số trang',
  S2: 'Đọc trang: chữ, bố cục, bảng',
  S3: 'Phân loại trang (chữ sẵn có / scan)',
  S4: 'AI2 nhận hồ sơ, bắt đầu phân tích',
  S5: 'Kiểm tra chất lượng kết quả',
  S6: 'Dựng cấu trúc điều khoản, bảng',
  S7: 'Trích xuất dữ kiện và trích dẫn',
  S8: 'Liên kết phụ lục',
  S9: 'So sánh, tìm mâu thuẫn',
  S10: 'Xếp hàng rà soát và chốt kết quả',
}

/**
 * Phần nào chạy bước nào, theo nơi BE ghi trạng thái bước (worker.py):
 * BE đánh dấu S0–S1 lúc nhận tệp; kết quả AI1 đánh dấu S2, S3, S8; kết quả
 * hoặc lỗi của AI2 đánh dấu S4–S7, S9, S10. FE chỉ hiển thị, không chạy bước nào.
 */
export const RUN_STEP_GROUPS = [
  {
    id: 'backend',
    label: 'Backend',
    hint: 'Nhận và kiểm tra tệp',
    steps: ['S0', 'S1'],
  },
  {
    id: 'ai1',
    label: 'Đọc tài liệu',
    hint: 'Đọc PDF thành chữ và ảnh trang',
    steps: ['S2', 'S3', 'S8'],
  },
  {
    id: 'ai2',
    label: 'Phân tích',
    hint: 'Cấu trúc, dữ kiện, mâu thuẫn',
    steps: ['S4', 'S5', 'S6', 'S7', 'S9', 'S10'],
  },
] as const satisfies readonly {
  id: string
  label: string
  hint: string
  steps: readonly (typeof RUN_STEP_ORDER)[number][]
}[]

/** Các bước AI2 chạy ngầm sau OCR; màn tiến trình không hiện các bước này. */
export const AI2_RUN_STEPS: readonly string[] = RUN_STEP_GROUPS.flatMap(
  (group) => (group.id === 'ai2' ? group.steps : []),
)

export function isAi2Step(code: string) {
  return AI2_RUN_STEPS.includes(code)
}

/** Các bước BE và AI1, theo thứ tự chạy: phần người dùng chờ trước khi xem cây. */
export const OCR_RUN_STEP_ORDER = RUN_STEP_ORDER.filter(
  (code) => !isAi2Step(code),
)

const AI1_RUN_STEPS: readonly string[] = RUN_STEP_GROUPS.flatMap((group) =>
  group.id === 'ai1' ? group.steps : [],
)

/** Các bước của màn tiến trình, kèm cờ bước nào là OCR của AI1. */
export const OCR_RUN_STEPS = OCR_RUN_STEP_ORDER.map((code) => ({
  code,
  ocr: AI1_RUN_STEPS.includes(code),
}))

/**
 * Trạng thái các bước của run mới nhất, để `analysisState` biết job dừng ở OCR
 * hay ở AI2. {} khi chưa có run; null khi không tải được (lỗi mạng...): khi đó
 * trang không được kết luận là "không phải lỗi AI2", mà phải khoá phần AI2.
 */
export async function loadStepStatuses(
  dossierId: string,
  signal?: AbortSignal,
): Promise<Record<string, RunStep> | null> {
  try {
    const runId = await findLatestRunId(dossierId, signal)
    if (!runId) return {}
    const rows = await listRunSteps(runId, signal)
    return Object.fromEntries(rows.map((row) => [row.step, row]))
  } catch {
    return null
  }
}

/**
 * Job vừa rời 'extracted' thì OCR chắc chắn đã xong (S8 xong), kể cả khi chưa
 * tải được các bước: dùng khi AI2 kết thúc lúc trang đang mở.
 */
export function stepsAfterAnalysis(
  steps: Record<string, { status: string }> | null,
): Record<string, { status: string }> {
  return { ...(steps ?? {}), S8: steps?.S8 ?? { status: 'succeeded' } }
}

/**
 * Tiến độ chung của AI2 từ các bước đã nhận: bước xong tính trọn, bước đang
 * chạy có `progress` tính phần đã xong. null khi chưa có số liệu nào.
 */
export function ai2ProgressPercent(steps: Record<string, RunStep>) {
  const rows = AI2_RUN_STEPS.flatMap((code) =>
    steps[code] ? [steps[code]] : [],
  )
  if (rows.length === 0) return null
  const done = rows.reduce(
    (sum, row) =>
      row.status === 'succeeded'
        ? sum + 1
        : row.status === 'running' && row.progress && row.progress.total > 0
          ? sum + Math.min(1, row.progress.done / row.progress.total)
          : sum,
    0,
  )
  return Math.min(99, Math.floor((done / AI2_RUN_STEPS.length) * 100))
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
    progress: parseStepProgress(data.progress),
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
        progress: parseStepProgress(row.progress),
      },
    ]
  })
}
