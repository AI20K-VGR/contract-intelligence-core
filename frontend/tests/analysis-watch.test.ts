import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ANALYSIS_STALL_MS,
  FALLBACK_POLL_MS,
  STALLED_POLL_MS,
  startAnalysisWatch,
  type AnalysisWatchDeps,
} from '../src/api/analysisWatch'
import { ApiError } from '../src/api/client'
import type { RunEvent, WatchRunHandlers } from '../src/api/runEvents'
import type { DossierStructure } from '../src/api/structure'

type WatchImpl = (
  handlers: WatchRunHandlers,
  signal: AbortSignal,
) => Promise<void>

// SSE mở tới khi bị đóng (quá 10 phút hoặc dừng theo dõi).
const openUntilClosed: WatchImpl = (_handlers, signal) =>
  new Promise((resolve) => {
    if (signal.aborted) resolve()
    signal.addEventListener('abort', () => resolve(), { once: true })
  })

function memoryStorage() {
  const map = new Map<string, string>()
  return {
    map,
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => void map.set(key, value),
    removeItem: (key: string) => void map.delete(key),
  }
}

function setup(watch: WatchImpl = openUntilClosed) {
  const job = { status: 'extracted' }
  const storage = memoryStorage()
  const deps: AnalysisWatchDeps = {
    findLatestRunId: vi.fn(async () => 'run_1'),
    listRunSteps: vi.fn(async () => []),
    getDossierStructure: vi.fn(
      async () => ({ latestJobStatus: job.status }) as DossierStructure,
    ),
    watchRun: vi.fn(async (_runId, handlers, signal) =>
      watch(handlers, signal),
    ),
    storage,
    now: () => Date.now(),
  }
  const handlers = {
    onPercent: vi.fn(),
    onStalled: vi.fn(),
    onDone: vi.fn(),
    onGone: vi.fn(),
  }
  return { job, storage, deps, handlers }
}

describe('startAnalysisWatch', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('finishes without opening SSE when AI2 is already done', async () => {
    const { job, deps, handlers } = setup()
    job.status = 'pending_review'
    startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(0)
    expect(handlers.onDone).toHaveBeenCalledTimes(1)
    expect(deps.watchRun).not.toHaveBeenCalled()
  })

  it('updates the percent from step.changed and finishes on run.completed', async () => {
    let push: ((event: RunEvent) => void) | null = null
    const { job, deps, handlers } = setup((h, signal) => {
      push = h.onEvent
      return openUntilClosed(h, signal)
    })
    startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(0)
    push!({
      id: '1',
      event: 'step.changed',
      data: {
        step: 'S6',
        status: 'running',
        progress: { done: 3, total: 6, unit: 'clause' },
      },
    })
    expect(handlers.onPercent).toHaveBeenLastCalledWith(8)
    job.status = 'pending_review'
    push!({ id: '2', event: 'run.completed', data: {} })
    await vi.advanceTimersByTimeAsync(0)
    expect(handlers.onDone).toHaveBeenCalledTimes(1)
  })

  it('falls back to asking every 15 s when SSE is rejected', async () => {
    const { job, deps, handlers } = setup(async (h) => h.onRejected(403))
    startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(0)
    const asked = vi.mocked(deps.getDossierStructure).mock.calls.length
    await vi.advanceTimersByTimeAsync(FALLBACK_POLL_MS)
    expect(deps.getDossierStructure).toHaveBeenCalledTimes(asked + 1)
    job.status = 'pending_review'
    await vi.advanceTimersByTimeAsync(FALLBACK_POLL_MS)
    expect(handlers.onDone).toHaveBeenCalledTimes(1)
  })

  it('past 10 minutes closes SSE, says so, and asks every 60 s until done', async () => {
    const { job, deps, handlers } = setup()
    startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(0)
    const stream = vi.mocked(deps.watchRun).mock.calls[0]![2]
    await vi.advanceTimersByTimeAsync(ANALYSIS_STALL_MS)
    expect(handlers.onStalled).toHaveBeenCalledTimes(1)
    expect(stream.aborted).toBe(true)
    const asked = vi.mocked(deps.getDossierStructure).mock.calls.length
    // Không hỏi theo nhịp 15 giây nữa.
    await vi.advanceTimersByTimeAsync(FALLBACK_POLL_MS)
    expect(deps.getDossierStructure).toHaveBeenCalledTimes(asked)
    await vi.advanceTimersByTimeAsync(STALLED_POLL_MS - FALLBACK_POLL_MS)
    expect(deps.getDossierStructure).toHaveBeenCalledTimes(asked + 1)
    // AI2 xong muộn: trang vẫn tự mở.
    job.status = 'pending_review'
    await vi.advanceTimersByTimeAsync(STALLED_POLL_MS)
    expect(handlers.onDone).toHaveBeenCalledTimes(1)
  })

  it('keeps counting the 10 minutes after leaving and coming back', async () => {
    const { deps, handlers, storage } = setup()
    storage.setItem(
      'ai2-watch-started:run_1',
      String(Date.now() - (ANALYSIS_STALL_MS - 60_000)),
    )
    startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(59_000)
    expect(handlers.onStalled).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1_000)
    expect(handlers.onStalled).toHaveBeenCalledTimes(1)
  })

  it('"Kiểm tra lại" (restart) gives a fresh 10 minutes', async () => {
    const { deps, handlers, storage } = setup()
    storage.setItem(
      'ai2-watch-started:run_1',
      String(Date.now() - ANALYSIS_STALL_MS * 2),
    )
    startAnalysisWatch('dos_1', handlers, { restart: true }, deps)
    await vi.advanceTimersByTimeAsync(ANALYSIS_STALL_MS - 1_000)
    expect(handlers.onStalled).not.toHaveBeenCalled()
  })

  it('forgets the start time once the job leaves extracted', async () => {
    const { job, deps, handlers, storage } = setup(async (h) =>
      h.onRejected(403),
    )
    startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(0)
    expect(storage.map.has('ai2-watch-started:run_1')).toBe(true)
    job.status = 'failed'
    await vi.advanceTimersByTimeAsync(FALLBACK_POLL_MS)
    expect(handlers.onDone).toHaveBeenCalledTimes(1)
    expect(storage.map.has('ai2-watch-started:run_1')).toBe(false)
  })

  it('still says it is stalled after 10 minutes when no run is found', async () => {
    const { deps, handlers } = setup()
    vi.mocked(deps.findLatestRunId).mockResolvedValue(null)
    startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(ANALYSIS_STALL_MS)
    expect(handlers.onStalled).toHaveBeenCalledTimes(1)
  })

  it('stops and says the dossier is gone on 403/404', async () => {
    const { deps, handlers } = setup(async (h) => h.onRejected(403))
    startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(0)
    vi.mocked(deps.getDossierStructure).mockRejectedValue(
      new ApiError(404, 'Not found'),
    )
    await vi.advanceTimersByTimeAsync(FALLBACK_POLL_MS)
    expect(handlers.onGone).toHaveBeenCalledTimes(1)
    const asked = vi.mocked(deps.getDossierStructure).mock.calls.length
    await vi.advanceTimersByTimeAsync(STALLED_POLL_MS * 3)
    expect(deps.getDossierStructure).toHaveBeenCalledTimes(asked)
    expect(handlers.onDone).not.toHaveBeenCalled()
  })

  it('keeps asking after a network error', async () => {
    const { job, deps, handlers } = setup(async (h) => h.onRejected(403))
    startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(0)
    vi.mocked(deps.getDossierStructure).mockRejectedValueOnce(
      new TypeError('Failed to fetch'),
    )
    await vi.advanceTimersByTimeAsync(FALLBACK_POLL_MS)
    job.status = 'pending_review'
    await vi.advanceTimersByTimeAsync(FALLBACK_POLL_MS)
    expect(handlers.onGone).not.toHaveBeenCalled()
    expect(handlers.onDone).toHaveBeenCalledTimes(1)
  })

  it('stops everything when the page leaves', async () => {
    const { deps, handlers } = setup()
    const stop = startAnalysisWatch('dos_1', handlers, {}, deps)
    await vi.advanceTimersByTimeAsync(0)
    stop()
    await vi.advanceTimersByTimeAsync(ANALYSIS_STALL_MS * 2)
    expect(handlers.onStalled).not.toHaveBeenCalled()
    expect(handlers.onDone).not.toHaveBeenCalled()
  })
})
