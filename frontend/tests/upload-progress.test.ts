import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/auth/oidc', () => ({
  getAccessToken: vi.fn(async () => 'token'),
  tenantIdFromToken: vi.fn(() => 'tenant-1'),
}))
vi.mock('../src/auth/sessionExpired', () => ({
  notifySessionExpired: vi.fn(),
  SESSION_EXPIRED_MESSAGE: 'Phiên đăng nhập đã hết hạn.',
}))

import {
  ApiError,
  postMultipartWithProgress,
  UPLOAD_STALL_TIMEOUT_MS,
  UPLOAD_STALLED_MESSAGE,
  UploadStalledError,
} from '../src/api/client'
import { createDossierErrorMessage } from '../src/api/dossiers'
import { notifySessionExpired } from '../src/auth/sessionExpired'

type Handler = ((event: ProgressEvent) => void) | null

/** Minimal XMLHttpRequest the test drives by hand: progress, upload end, response. */
class FakeXhr {
  static last: FakeXhr | null = null
  upload: { onprogress: Handler; onload: Handler } = {
    onprogress: null,
    onload: null,
  }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  status = 0
  responseText = ''
  headers: Record<string, string> = {}
  method = ''
  url = ''
  aborted = false
  sent: unknown = null

  constructor() {
    FakeXhr.last = this
  }
  open(method: string, url: string) {
    this.method = method
    this.url = url
  }
  setRequestHeader(key: string, value: string) {
    this.headers[key.toLowerCase()] = value
  }
  send(body: unknown) {
    this.sent = body
  }
  abort() {
    this.aborted = true
    this.onabort?.()
  }
  progress(loaded: number, total: number) {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded,
      total,
    } as ProgressEvent)
  }
  uploadDone() {
    this.upload.onload?.({} as ProgressEvent)
  }
  respond(status: number, body: unknown) {
    this.status = status
    this.responseText = JSON.stringify(body)
    this.onload?.()
  }
}

async function started() {
  // getAccessToken is awaited before the request opens.
  await vi.waitFor(() => expect(FakeXhr.last).not.toBeNull())
  return FakeXhr.last as FakeXhr
}

describe('postMultipartWithProgress', () => {
  beforeEach(() => {
    FakeXhr.last = null
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    vi.mocked(notifySessionExpired).mockClear()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('reports bytes sent and returns the envelope data', async () => {
    const onProgress = vi.fn()
    const form = new FormData()
    const pending = postMultipartWithProgress<{ dossier_id: string }>(
      '/api/v1/dossiers',
      form,
      { onProgress },
    )
    const xhr = await started()
    expect(xhr.method).toBe('POST')
    expect(xhr.url).toMatch(/\/api\/v1\/dossiers$/)
    expect(xhr.sent).toBe(form)
    expect(xhr.headers.authorization).toBe('Bearer token')
    expect(xhr.headers['x-tenant-id']).toBe('tenant-1')
    expect(xhr.headers['content-type']).toBeUndefined()

    xhr.progress(1_000, 4_000)
    xhr.progress(4_000, 4_000)
    xhr.uploadDone()
    xhr.respond(202, { data: { dossier_id: 'dos_1' } })

    await expect(pending).resolves.toEqual({
      data: { dossier_id: 'dos_1' },
      meta: undefined,
    })
    expect(onProgress.mock.calls).toEqual([
      [1_000, 4_000],
      [4_000, 4_000],
    ])
  })

  it('aborts with the network message after 30 s without a byte sent', async () => {
    vi.useFakeTimers()
    const pending = postMultipartWithProgress(
      '/api/v1/dossiers',
      new FormData(),
    )
    const rejection = expect(pending).rejects.toBeInstanceOf(UploadStalledError)
    const xhr = await started()
    xhr.progress(500, 4_000)

    await vi.advanceTimersByTimeAsync(UPLOAD_STALL_TIMEOUT_MS - 1)
    expect(xhr.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(1)

    await rejection
    expect(xhr.aborted).toBe(true)
    await expect(pending).rejects.toThrow(UPLOAD_STALLED_MESSAGE)
  })

  it('keeps going while bytes still move, however slowly', async () => {
    vi.useFakeTimers()
    const pending = postMultipartWithProgress(
      '/api/v1/dossiers',
      new FormData(),
    )
    const xhr = await started()
    for (let sent = 1; sent <= 5; sent += 1) {
      await vi.advanceTimersByTimeAsync(UPLOAD_STALL_TIMEOUT_MS - 1_000)
      xhr.progress(sent * 100, 500)
    }
    expect(xhr.aborted).toBe(false)
    xhr.uploadDone()
    xhr.respond(202, { data: { dossier_id: 'dos_2' } })
    await expect(pending).resolves.toMatchObject({
      data: { dossier_id: 'dos_2' },
    })
  })

  it('does not time out while the server works after the body is sent', async () => {
    vi.useFakeTimers()
    const pending = postMultipartWithProgress(
      '/api/v1/dossiers',
      new FormData(),
    )
    const xhr = await started()
    xhr.progress(500, 500)
    xhr.uploadDone()
    await vi.advanceTimersByTimeAsync(UPLOAD_STALL_TIMEOUT_MS * 3)
    expect(xhr.aborted).toBe(false)
    xhr.respond(202, { data: { dossier_id: 'dos_3' } })
    await expect(pending).resolves.toMatchObject({
      data: { dossier_id: 'dos_3' },
    })
  })

  it('maps an error body like requestJson, and 401 ends the session', async () => {
    const pending = postMultipartWithProgress(
      '/api/v1/dossiers',
      new FormData(),
    )
    const xhr = await started()
    xhr.respond(401, { detail: 'Token has expired' })
    const error = await pending.catch((cause: unknown) => cause)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(401)
    expect((error as ApiError).message).toBe('Phiên đăng nhập đã hết hạn.')
    expect(notifySessionExpired).toHaveBeenCalledOnce()
  })

  it('rejects a dropped connection as a TypeError, like fetch', async () => {
    const pending = postMultipartWithProgress(
      '/api/v1/dossiers',
      new FormData(),
    )
    const xhr = await started()
    xhr.onerror?.()
    await expect(pending).rejects.toBeInstanceOf(TypeError)
  })

  it('stops when the caller aborts', async () => {
    const controller = new AbortController()
    const pending = postMultipartWithProgress(
      '/api/v1/dossiers',
      new FormData(),
      {
        signal: controller.signal,
      },
    )
    const xhr = await started()
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect(xhr.aborted).toBe(true)
  })
})

describe('upload messages', () => {
  it('shows the stall message to the user', () => {
    expect(createDossierErrorMessage(new UploadStalledError())).toBe(
      'Mạng chậm hoặc bị ngắt, vui lòng thử lại.',
    )
  })
})
