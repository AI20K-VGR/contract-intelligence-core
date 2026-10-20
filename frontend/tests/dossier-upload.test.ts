import { beforeEach, describe, expect, it, vi } from 'vitest'

const createDossier = vi.fn()
const patchDossier = vi.fn()
const splitDossier = vi.fn()
const getDossierStructure = vi.fn()

vi.mock('../src/api/dossiers', async () => {
  const actual = await vi.importActual<typeof import('../src/api/dossiers')>(
    '../src/api/dossiers',
  )
  return { ...actual, createDossier, patchDossier, splitDossier }
})

vi.mock('../src/api/structure', () => ({ getDossierStructure }))

vi.mock('../src/pdf/imageToPdf', () => ({
  asUploadPdf: (file: File) => Promise.resolve(file),
}))

const { ApiError } = await import('../src/api/client')
const {
  cancelDossierUpload,
  getDossierUpload,
  startDossierUpload,
  uploadPercent,
} = await import('../src/api/dossierUpload')

function input() {
  return {
    name: 'Hồ sơ A',
    code: 'HD-01',
    structureMode: 'numbered' as const,
    contract: new File([new Uint8Array(1000)], 'hd.pdf', {
      type: 'application/pdf',
    }),
    annexes: [],
    splitPending: false,
  }
}

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

describe('dossier upload', () => {
  beforeEach(() => {
    createDossier.mockReset()
    patchDossier.mockReset()
    patchDossier.mockResolvedValue({})
  })

  it('reports bytes sent, then the created dossier', async () => {
    let report: (sent: number, total: number) => void = () => undefined
    let finish: (value: unknown) => void = () => undefined
    createDossier.mockImplementation(
      (_body, options: { onProgress: typeof report }) => {
        report = options.onProgress
        return new Promise((resolve) => {
          finish = resolve
        })
      },
    )

    const id = startDossierUpload(input())
    await settle()
    report(250, 1000)
    expect(getDossierUpload(id)?.status).toBe('sending')
    expect(uploadPercent(getDossierUpload(id)!)).toBe(25)

    report(1000, 1000)
    expect(getDossierUpload(id)?.status).toBe('saving')

    finish({ dossier_id: 'dos_1' })
    await settle()
    const done = getDossierUpload(id)!
    expect(done.status).toBe('done')
    expect(done.dossierId).toBe('dos_1')
    // Tệp không cần giữ nữa khi đã tạo hồ sơ.
    expect(done.input).toBeNull()
    expect(patchDossier).toHaveBeenCalledWith('dos_1', {
      metadata: {
        privacy: 'private',
        structure_mode: 'numbered',
        code: 'HD-01',
      },
    })
  })

  it('keeps the picked files and the message when the server refuses', async () => {
    createDossier.mockRejectedValue(new ApiError(403, 'Forbidden'))

    const id = startDossierUpload(input())
    await settle()

    const failed = getDossierUpload(id)!
    expect(failed.status).toBe('failed')
    expect(failed.error).toBe('Chỉ vận hành và quản trị mới tải hồ sơ được.')
    expect(failed.input?.contract.name).toBe('hd.pdf')
  })

  it('cancels only while bytes are still being sent', async () => {
    let report: (sent: number, total: number) => void = () => undefined
    createDossier.mockImplementation(
      (_body, options: { onProgress: typeof report; signal: AbortSignal }) => {
        report = options.onProgress
        return new Promise((_resolve, reject) => {
          options.signal.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          )
        })
      },
    )

    const saving = startDossierUpload(input())
    await settle()
    report(1000, 1000)
    expect(cancelDossierUpload(saving)).toBe(false)

    const sending = startDossierUpload(input())
    await settle()
    report(10, 1000)
    expect(cancelDossierUpload(sending)).toBe(true)
    await settle()
    expect(getDossierUpload(sending)?.status).toBe('cancelled')
    expect(getDossierUpload(sending)?.input).not.toBeNull()
  })
})

describe('dossier upload stall', () => {
  it('fails with the stalled message so the user can retry', async () => {
    const { UploadStalledError, UPLOAD_STALLED_MESSAGE } =
      await import('../src/api/client')
    createDossier.mockReset()
    createDossier.mockRejectedValue(new UploadStalledError())

    const id = startDossierUpload(input())
    await settle()

    const failed = getDossierUpload(id)!
    expect(failed.status).toBe('failed')
    expect(failed.error).toBe(UPLOAD_STALLED_MESSAGE)
    expect(failed.input).not.toBeNull()
  })
})

describe('dossier upload memory', () => {
  it('drops failed uploads when a new one starts, and when the form takes the files back', async () => {
    const { releaseDossierUpload } = await import('../src/api/dossierUpload')
    createDossier.mockReset()
    createDossier.mockRejectedValue(new ApiError(500, 'boom'))

    const first = startDossierUpload(input())
    await settle()
    expect(getDossierUpload(first)?.status).toBe('failed')

    const second = startDossierUpload(input())
    expect(getDossierUpload(first)).toBeNull()
    await settle()
    expect(getDossierUpload(second)?.status).toBe('failed')

    releaseDossierUpload(second)
    expect(getDossierUpload(second)).toBeNull()
  })

  it('keeps an upload that is still sending when asked to release it', async () => {
    const { releaseDossierUpload } = await import('../src/api/dossierUpload')
    createDossier.mockReset()
    createDossier.mockReturnValue(new Promise(() => undefined))

    const id = startDossierUpload(input())
    await settle()
    releaseDossierUpload(id)
    expect(getDossierUpload(id)?.status).toBe('sending')
  })
})

describe('merged file the browser could not cut', () => {
  const parts = [
    { page_start: 1, page_end: 3, role: 'contract' as const },
    { page_start: 4, page_end: 5, role: 'annex' as const },
  ]

  beforeEach(() => {
    createDossier.mockReset()
    patchDossier.mockReset()
    patchDossier.mockResolvedValue({})
    splitDossier.mockReset()
    getDossierStructure.mockReset()
    getDossierStructure.mockResolvedValue({
      documents: [{ id: 'doc_1', role: 'contract' }],
    })
  })

  it('uploads the whole file as split_pending, then splits it on the server', async () => {
    createDossier.mockResolvedValue({ dossier_id: 'dos_9', job_id: null })
    splitDossier.mockResolvedValue({})

    const id = startDossierUpload({
      ...input(),
      splitPending: true,
      serverSplit: parts,
    })
    await settle()

    expect(createDossier.mock.calls[0][0].metadata).toEqual({
      name: 'Hồ sơ A',
      split_pending: true,
    })
    expect(splitDossier).toHaveBeenCalledWith('dos_9', 'doc_1', parts)
    expect(getDossierUpload(id)?.status).toBe('done')
  })

  it('still finishes the upload when the split is refused', async () => {
    createDossier.mockResolvedValue({ dossier_id: 'dos_9', job_id: null })
    splitDossier.mockRejectedValue(new ApiError(422, 'bad parts'))

    const id = startDossierUpload({
      ...input(),
      splitPending: true,
      serverSplit: parts,
    })
    await settle()

    // Hồ sơ vẫn chờ tách: trang tiến trình đưa người dùng sang trang tách file.
    const done = getDossierUpload(id)!
    expect(done.status).toBe('done')
    expect(done.dossierId).toBe('dos_9')
  })

  it('does not split a file the browser already cut', async () => {
    createDossier.mockResolvedValue({ dossier_id: 'dos_1', job_id: null })

    startDossierUpload(input())
    await settle()

    expect(createDossier.mock.calls[0][0].metadata).toEqual({ name: 'Hồ sơ A' })
    expect(splitDossier).not.toHaveBeenCalled()
  })
})
