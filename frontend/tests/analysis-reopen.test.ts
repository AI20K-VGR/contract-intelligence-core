import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  REOPEN_FAST_MS,
  REOPEN_FAST_TRIES,
  REOPEN_LIMIT_MS,
  waitForAnalysisReopen,
} from '../src/api/analysisReopen'
import type { DossierStructure } from '../src/api/structure'

function setup() {
  const job = { status: 'failed' }
  const current = { value: true }
  const deps = {
    getDossierStructure: vi.fn(
      async () => ({ latestJobStatus: job.status }) as DossierStructure,
    ),
    isCurrent: () => current.value,
    onSlow: vi.fn(),
  }
  return { job, current, deps }
}

describe('waitForAnalysisReopen', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns the job once the worker reopens it', async () => {
    const { job, deps } = setup()
    const result = waitForAnalysisReopen('dos_1', deps)
    await vi.advanceTimersByTimeAsync(REOPEN_FAST_MS)
    job.status = 'extracted'
    await vi.advanceTimersByTimeAsync(REOPEN_FAST_MS)
    await expect(result).resolves.toMatchObject({ kind: 'reopened' })
    expect(deps.onSlow).not.toHaveBeenCalled()
  })

  it('also waits out a cancelled job resumed after OCR', async () => {
    // Chạy tiếp sau huỷ: job 'cancelled' sang lại 'extracted', trang cây ở lại.
    const { job, deps } = setup()
    job.status = 'cancelled'
    const result = waitForAnalysisReopen('dos_1', deps)
    await vi.advanceTimersByTimeAsync(REOPEN_FAST_MS)
    expect(deps.getDossierStructure).toHaveBeenCalledTimes(1)
    job.status = 'extracted'
    await vi.advanceTimersByTimeAsync(REOPEN_FAST_MS)
    await expect(result).resolves.toMatchObject({
      kind: 'reopened',
      next: { latestJobStatus: 'extracted' },
    })
  })

  it('says it is slow after the fast tries, and gives up after 5 minutes', async () => {
    // AI2 lỗi lại nhanh hơn nhịp hỏi: job luôn 'failed', trang không chờ mãi.
    const { deps } = setup()
    const result = waitForAnalysisReopen('dos_1', deps)
    await vi.advanceTimersByTimeAsync(REOPEN_FAST_MS * REOPEN_FAST_TRIES)
    expect(deps.onSlow).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(REOPEN_LIMIT_MS)
    await expect(result).resolves.toEqual({ kind: 'timeout' })
    const asked = deps.getDossierStructure.mock.calls.length
    await vi.advanceTimersByTimeAsync(REOPEN_LIMIT_MS)
    expect(deps.getDossierStructure).toHaveBeenCalledTimes(asked)
  })

  it('stops when a newer wait starts or the page leaves', async () => {
    const { current, deps } = setup()
    const result = waitForAnalysisReopen('dos_1', deps)
    await vi.advanceTimersByTimeAsync(REOPEN_FAST_MS)
    current.value = false
    await vi.advanceTimersByTimeAsync(REOPEN_FAST_MS)
    await expect(result).resolves.toEqual({ kind: 'abandoned' })
    expect(deps.getDossierStructure).toHaveBeenCalledTimes(1)
  })

  it('keeps asking after a network error', async () => {
    const { job, deps } = setup()
    deps.getDossierStructure.mockRejectedValueOnce(
      new TypeError('Failed to fetch'),
    )
    const result = waitForAnalysisReopen('dos_1', deps)
    await vi.advanceTimersByTimeAsync(REOPEN_FAST_MS)
    job.status = 'extracted'
    await vi.advanceTimersByTimeAsync(REOPEN_FAST_MS)
    await expect(result).resolves.toMatchObject({ kind: 'reopened' })
  })
})
