import { describe, expect, it, vi } from 'vitest'
import { ApiError, UploadStalledError } from '../src/api/client'
import { createDossierErrorMessage } from '../src/api/dossiers'
import {
  CHUNK_ATTEMPTS,
  uploadDossierInChunks,
  type ChunkedUploadDeps,
  type UploadSession,
} from '../src/api/chunkedUpload'

const CHUNK = 4

function pdf(name: string, size: number) {
  return new File([new Uint8Array(size).fill(7)], name, {
    type: 'application/pdf',
  })
}

function session(
  files: { size: number; received?: number[] }[],
  extra: Partial<UploadSession> = {},
): UploadSession {
  return {
    upload_id: 'up_1',
    status: 'open',
    chunk_size: CHUNK,
    expires_at: '2026-10-20T00:00:00Z',
    files: files.map((file, index) => ({
      index,
      role: index === 0 ? 'contract' : 'annex',
      filename: `f${index}.pdf`,
      size: file.size,
      chunks: Math.ceil(file.size / CHUNK),
      received: file.received ?? [],
    })),
    ...extra,
  }
}

function setup(opened: UploadSession) {
  const deps: ChunkedUploadDeps = {
    openSession: vi.fn(async () => opened),
    getSession: vi.fn(async () => opened),
    sendChunk: vi.fn(async () => {}),
    complete: vi.fn(async () => ({ dossier_id: 'dos_1', job_id: 'job_1' })),
    cancel: vi.fn(async () => {}),
    legacyCreate: vi.fn(async () => ({ dossier_id: 'dos_old', job_id: null })),
    sleep: vi.fn(async () => {}),
  }
  return deps
}

const input = (contractSize = 10, annexSize = 5) => ({
  contract: pdf('hop-dong.pdf', contractSize),
  annexes: [pdf('phu-luc.pdf', annexSize)],
  metadata: { name: 'Hồ sơ A' },
})

describe('uploadDossierInChunks (#145)', () => {
  it('declares the files, sends every chunk with the right size, then completes', async () => {
    const deps = setup(session([{ size: 10 }, { size: 5 }]))
    const progress: [number, number][] = []
    const created = await uploadDossierInChunks(
      input(),
      { onProgress: (sent, total) => progress.push([sent, total]) },
      deps,
    )
    expect(created).toEqual({ dossier_id: 'dos_1', job_id: 'job_1' })
    expect(deps.openSession).toHaveBeenCalledWith(
      {
        metadata: { name: 'Hồ sơ A' },
        files: [
          { role: 'contract', filename: 'hop-dong.pdf', size: 10 },
          { role: 'annex', filename: 'phu-luc.pdf', size: 5 },
        ],
      },
      undefined,
    )
    const calls = vi.mocked(deps.sendChunk).mock.calls
    expect(calls.map(([path]) => path)).toEqual([
      '/api/v1/uploads/up_1/files/0/chunks/0',
      '/api/v1/uploads/up_1/files/0/chunks/1',
      '/api/v1/uploads/up_1/files/0/chunks/2',
      '/api/v1/uploads/up_1/files/1/chunks/0',
      '/api/v1/uploads/up_1/files/1/chunks/1',
    ])
    expect(calls.map(([, blob]) => blob.size)).toEqual([4, 4, 2, 4, 1])
    expect(progress.at(-1)).toEqual([15, 15])
    expect(deps.complete).toHaveBeenCalledTimes(1)
    expect(deps.cancel).not.toHaveBeenCalled()
  })

  it('resends only the chunk that failed on a dropped connection or a stall', async () => {
    const deps = setup(session([{ size: 8 }]))
    vi.mocked(deps.sendChunk)
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockRejectedValueOnce(new UploadStalledError())
    await uploadDossierInChunks(
      { contract: pdf('a.pdf', 8), metadata: {} },
      {},
      deps,
    )
    const paths = vi.mocked(deps.sendChunk).mock.calls.map(([path]) => path)
    // Khúc 0 gửi 3 lần (2 lần lỗi tạm), khúc 1 một lần.
    expect(paths.filter((p) => p.endsWith('/chunks/0'))).toHaveLength(3)
    expect(paths.filter((p) => p.endsWith('/chunks/1'))).toHaveLength(1)
    expect(deps.sleep).toHaveBeenCalledTimes(2)
  })

  it('gives up after a few attempts, and drops the session', async () => {
    const deps = setup(session([{ size: 4 }]))
    vi.mocked(deps.sendChunk).mockRejectedValue(
      new TypeError('Failed to fetch'),
    )
    await expect(
      uploadDossierInChunks(
        { contract: pdf('a.pdf', 4), metadata: {} },
        {},
        deps,
      ),
    ).rejects.toBeInstanceOf(TypeError)
    expect(deps.sendChunk).toHaveBeenCalledTimes(CHUNK_ATTEMPTS)
    expect(deps.cancel).toHaveBeenCalledWith('up_1')
  })

  it('does not retry a refused chunk (422) and drops the session', async () => {
    const deps = setup(session([{ size: 4 }]))
    vi.mocked(deps.sendChunk).mockRejectedValue(
      new ApiError(422, 'Chunk 0 of file 0 must be 4 bytes'),
    )
    await expect(
      uploadDossierInChunks(
        { contract: pdf('a.pdf', 4), metadata: {} },
        {},
        deps,
      ),
    ).rejects.toBeInstanceOf(ApiError)
    expect(deps.sendChunk).toHaveBeenCalledTimes(1)
    expect(deps.cancel).toHaveBeenCalledWith('up_1')
  })

  it('sends the chunks the server says are missing, then completes again', async () => {
    const deps = setup(session([{ size: 8 }]))
    vi.mocked(deps.complete)
      .mockRejectedValueOnce(
        new ApiError(409, 'Missing chunks', 'UPLOAD_MISSING_CHUNKS', {
          error: {
            code: 'UPLOAD_MISSING_CHUNKS',
            message: 'Missing chunks',
            details: { missing_chunks: { '0': [1] } },
          },
        }),
      )
      .mockResolvedValueOnce({ dossier_id: 'dos_1', job_id: 'job_1' })
    const created = await uploadDossierInChunks(
      { contract: pdf('a.pdf', 8), metadata: {} },
      {},
      deps,
    )
    expect(created.dossier_id).toBe('dos_1')
    const paths = vi.mocked(deps.sendChunk).mock.calls.map(([path]) => path)
    expect(paths.filter((p) => p.endsWith('/chunks/1'))).toHaveLength(2)
    expect(deps.complete).toHaveBeenCalledTimes(2)
  })

  it('waits for the dossier when complete is cut (524) or still completing', async () => {
    const deps = setup(session([{ size: 4 }]))
    vi.mocked(deps.complete).mockRejectedValueOnce(
      new ApiError(524, 'A timeout occurred'),
    )
    vi.mocked(deps.getSession).mockResolvedValueOnce(
      session([{ size: 4, received: [0] }], {
        status: 'completed',
        dossier_id: 'dos_9',
        job_id: 'job_9',
      }),
    )
    const created = await uploadDossierInChunks(
      { contract: pdf('a.pdf', 4), metadata: {} },
      {},
      deps,
    )
    // Không tạo hồ sơ thứ hai: lấy hồ sơ của lần complete đã chạy xong ở server.
    expect(created).toEqual({ dossier_id: 'dos_9', job_id: 'job_9' })
    expect(deps.complete).toHaveBeenCalledTimes(1)
    expect(deps.cancel).not.toHaveBeenCalled()
  })

  it('skips the chunks the session already has (resume)', async () => {
    const deps = setup(session([{ size: 8, received: [0] }]))
    await uploadDossierInChunks(
      { contract: pdf('a.pdf', 8), metadata: {} },
      {},
      deps,
    )
    const paths = vi.mocked(deps.sendChunk).mock.calls.map(([path]) => path)
    expect(paths).toEqual(['/api/v1/uploads/up_1/files/0/chunks/1'])
  })

  it('falls back to one POST /dossiers on a backend without /uploads', async () => {
    const deps = setup(session([{ size: 4 }]))
    vi.mocked(deps.openSession).mockRejectedValue(
      new ApiError(404, 'Not Found'),
    )
    const created = await uploadDossierInChunks(
      { contract: pdf('a.pdf', 4), metadata: {} },
      {},
      deps,
    )
    expect(created.dossier_id).toBe('dos_old')
    expect(deps.sendChunk).not.toHaveBeenCalled()
  })

  it('drops the session when the user cancels', async () => {
    const controller = new AbortController()
    const deps = setup(session([{ size: 8 }]))
    vi.mocked(deps.sendChunk).mockImplementationOnce(async () => {
      controller.abort()
      throw new DOMException('Aborted', 'AbortError')
    })
    await expect(
      uploadDossierInChunks(
        { contract: pdf('a.pdf', 8), metadata: {} },
        { signal: controller.signal },
        deps,
      ),
    ).rejects.toMatchObject({ name: 'AbortError' })
    expect(deps.cancel).toHaveBeenCalledWith('up_1')
    expect(deps.complete).not.toHaveBeenCalled()
  })
})

describe('upload error codes (DOC-05b v4.2.0 §3.3)', () => {
  const coded = (status: number, code: string, details: unknown = {}) =>
    new ApiError(status, code, code, {
      error: { code, message: code, details },
    })

  it('waits on UPLOAD_COMPLETING and takes the dossier once completed', async () => {
    const deps = setup(session([{ size: 4 }]))
    vi.mocked(deps.complete).mockRejectedValueOnce(
      coded(409, 'UPLOAD_COMPLETING'),
    )
    vi.mocked(deps.getSession).mockResolvedValueOnce(
      session([{ size: 4, received: [0] }], {
        status: 'completed',
        dossier_id: 'dos_7',
        job_id: 'job_7',
      }),
    )
    const created = await uploadDossierInChunks(
      { contract: pdf('a.pdf', 4), metadata: {} },
      {},
      deps,
    )
    expect(created).toEqual({ dossier_id: 'dos_7', job_id: 'job_7' })
    expect(deps.cancel).not.toHaveBeenCalled()
  })

  it('takes the dossier of UPLOAD_COMPLETED instead of uploading again', async () => {
    const deps = setup(session([{ size: 8 }]))
    vi.mocked(deps.sendChunk).mockRejectedValueOnce(
      coded(409, 'UPLOAD_COMPLETED', { dossier_id: 'dos_5' }),
    )
    vi.mocked(deps.getSession).mockRejectedValueOnce(
      new TypeError('Failed to fetch'),
    )
    const created = await uploadDossierInChunks(
      { contract: pdf('a.pdf', 8), metadata: {} },
      {},
      deps,
    )
    expect(created.dossier_id).toBe('dos_5')
    expect(deps.cancel).not.toHaveBeenCalled()
  })

  it('stops on UPLOAD_CANCELLED (a newer upload evicted this one) without retrying', async () => {
    const deps = setup(session([{ size: 4 }]))
    vi.mocked(deps.sendChunk).mockRejectedValue(coded(409, 'UPLOAD_CANCELLED'))
    const failure = await uploadDossierInChunks(
      { contract: pdf('a.pdf', 4), metadata: {} },
      {},
      deps,
    ).catch((cause: unknown) => cause)
    expect(deps.sendChunk).toHaveBeenCalledTimes(1)
    expect(createDossierErrorMessage(failure)).toContain('lượt tải lên mới hơn')
  })

  it('says 3 uploads are still running when opening a session gets 429', async () => {
    const deps = setup(session([{ size: 4 }]))
    vi.mocked(deps.openSession).mockRejectedValueOnce(
      new ApiError(
        429,
        'Too many uploads in progress; finish or cancel one, or try again in a few minutes.',
      ),
    )
    const failure = await uploadDossierInChunks(
      { contract: pdf('a.pdf', 4), metadata: {} },
      {},
      deps,
    ).catch((cause: unknown) => cause)
    expect(deps.sendChunk).not.toHaveBeenCalled()
    expect(deps.legacyCreate).not.toHaveBeenCalled()
    expect(createDossierErrorMessage(failure)).toBe(
      'Đang có 3 lượt tải lên chưa xong. Chờ một lượt xong hoặc huỷ bớt rồi thử lại.',
    )
  })

  it('words every upload code in Vietnamese', () => {
    for (const code of [
      'UPLOAD_CANCELLED',
      'UPLOAD_NOT_OPEN',
      'UPLOAD_EXPIRED',
      'UPLOAD_SIZE_MISMATCH',
      'UPLOAD_COMPLETING',
      'UPLOAD_MISSING_CHUNKS',
    ]) {
      const message = createDossierErrorMessage(coded(409, code)) ?? ''
      expect(message).toMatch(/tải|tệp|ghép/)
      expect(message).not.toContain(code)
    }
  })
})

describe('complete retries (PR #149 review)', () => {
  it('reads the session after a dropped connection on complete instead of failing', async () => {
    // Server đã tạo hồ sơ nhưng phản hồi mất giữa đường: không báo lỗi, không tải lại.
    const deps = setup(session([{ size: 4 }]))
    vi.mocked(deps.complete).mockRejectedValueOnce(
      new TypeError('Failed to fetch'),
    )
    vi.mocked(deps.getSession).mockResolvedValueOnce(
      session([{ size: 4, received: [0] }], {
        status: 'completed',
        dossier_id: 'dos_3',
        job_id: 'job_3',
      }),
    )
    const created = await uploadDossierInChunks(
      { contract: pdf('a.pdf', 4), metadata: {} },
      {},
      deps,
    )
    expect(created).toEqual({ dossier_id: 'dos_3', job_id: 'job_3' })
    expect(deps.cancel).not.toHaveBeenCalled()
  })

  it('does not retry complete on a plain 500', async () => {
    const deps = setup(session([{ size: 4 }]))
    vi.mocked(deps.complete).mockRejectedValueOnce(new ApiError(500, 'boom'))
    await expect(
      uploadDossierInChunks(
        { contract: pdf('a.pdf', 4), metadata: {} },
        {},
        deps,
      ),
    ).rejects.toMatchObject({ status: 500 })
    expect(deps.complete).toHaveBeenCalledTimes(1)
    expect(deps.getSession).not.toHaveBeenCalled()
  })
})
