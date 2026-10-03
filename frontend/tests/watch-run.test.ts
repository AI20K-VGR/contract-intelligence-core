import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiFetch = vi.fn()
vi.mock('../src/api/client', () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
  getJson: vi.fn(),
}))

import { watchRun } from '../src/api/runEvents'

function sse(
  text: string,
  { hold = false, signal }: { hold?: boolean; signal?: AbortSignal } = {},
) {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text))
      if (hold) {
        signal?.addEventListener('abort', () =>
          controller.error(new DOMException('aborted', 'AbortError')),
        )
      } else {
        controller.close()
      }
    },
  })
  return new Response(body, { status: 200 })
}

function handlers() {
  return {
    onEvent: vi.fn(),
    onLost: vi.fn(),
    onRejected: vi.fn(),
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('window', globalThis)
  apiFetch.mockReset()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('watchRun', () => {
  it('stops after run.completed without asking again', async () => {
    apiFetch.mockResolvedValueOnce(
      sse(
        'id: 1\nevent: step.changed\ndata: {"step":"S2"}\n\nevent: run.completed\ndata: {}\n\n',
      ),
    )
    const h = handlers()
    await watchRun('run_1', h, new AbortController().signal)
    expect(apiFetch).toHaveBeenCalledTimes(1)
    expect(h.onLost).not.toHaveBeenCalled()
    expect(h.onEvent).toHaveBeenCalledTimes(2)
  })

  it('on lost connection asks once, then reconnects with Last-Event-ID', async () => {
    apiFetch
      .mockResolvedValueOnce(
        sse('id: 5\nevent: step.changed\ndata: {"step":"S2"}\n\n'),
      )
      .mockResolvedValueOnce(sse('event: run.completed\ndata: {}\n\n'))
    const h = handlers()
    const done = watchRun('run_1', h, new AbortController().signal)
    await vi.advanceTimersByTimeAsync(1500)
    await done
    expect(h.onLost).toHaveBeenCalledTimes(1)
    expect(apiFetch).toHaveBeenCalledTimes(2)
    const second = apiFetch.mock.calls[1][1] as {
      headers: Record<string, string>
    }
    expect(second.headers['Last-Event-ID']).toBe('5')
  })

  it('retries with growing delay while the server is down', async () => {
    apiFetch.mockRejectedValue(new Error('network'))
    const h = handlers()
    const controller = new AbortController()
    const done = watchRun('run_1', h, controller.signal)
    await vi.advanceTimersByTimeAsync(1000) // 1st wait
    await vi.advanceTimersByTimeAsync(2000) // 2nd wait
    expect(apiFetch).toHaveBeenCalledTimes(3)
    controller.abort()
    await done
  })

  it('disconnects when the page is left (abort) and does not reconnect', async () => {
    const controller = new AbortController()
    apiFetch.mockImplementation(
      (_path: string, init: { signal: AbortSignal }) =>
        Promise.resolve(
          sse('event: run.started\ndata: {}\n\n', {
            hold: true,
            signal: init.signal,
          }),
        ),
    )
    const h = handlers()
    const done = watchRun('run_1', h, controller.signal)
    await vi.advanceTimersByTimeAsync(50)
    expect(h.onEvent).toHaveBeenCalledTimes(1)
    controller.abort()
    await done
    await vi.advanceTimersByTimeAsync(60000)
    expect(apiFetch).toHaveBeenCalledTimes(1)
    expect(h.onLost).not.toHaveBeenCalled()
  })

  it('does not reconnect when the server rejects (403/404)', async () => {
    apiFetch.mockResolvedValueOnce(new Response('no', { status: 403 }))
    const h = handlers()
    await watchRun('run_1', h, new AbortController().signal)
    expect(h.onRejected).toHaveBeenCalledWith(403)
    expect(apiFetch).toHaveBeenCalledTimes(1)
  })
})
