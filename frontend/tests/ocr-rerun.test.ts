import { beforeEach, describe, expect, it, vi } from 'vitest'

const requestJson = vi.fn()

vi.mock('../src/api/client', async () => {
  const actual =
    await vi.importActual<typeof import('../src/api/client')>(
      '../src/api/client',
    )
  return { ...actual, requestJson }
})

const { ApiError } = await import('../src/api/client')
const { rerunDossierOcr } = await import('../src/api/dossiers')

function paths() {
  return requestJson.mock.calls.map((call) => call[0] as string)
}

describe('rerunDossierOcr', () => {
  beforeEach(() => requestJson.mockReset())

  it('re-runs only the failed part, keeping pages already OCR-ed', async () => {
    requestJson.mockResolvedValueOnce({ data: { status: 'queued' } })

    await expect(rerunDossierOcr('dos_1')).resolves.toBe('retry-failed')

    expect(paths()).toEqual(['/api/v1/dossiers/dos_1/ocr/retry-failed'])
  })

  it('restarts in full only when there is no failed part (409)', async () => {
    requestJson
      .mockRejectedValueOnce(new ApiError(409, 'not failed at OCR'))
      .mockResolvedValueOnce({ data: { status: 'queued' } })

    await expect(rerunDossierOcr('dos_1')).resolves.toBe('restart')

    expect(paths()).toEqual([
      '/api/v1/dossiers/dos_1/ocr/retry-failed',
      '/api/v1/dossiers/dos_1/ocr',
    ])
  })

  it('does not restart on any other error', async () => {
    requestJson.mockRejectedValueOnce(new ApiError(500, 'boom'))

    await expect(rerunDossierOcr('dos_1')).rejects.toThrow('boom')

    expect(paths()).toEqual(['/api/v1/dossiers/dos_1/ocr/retry-failed'])
  })
})
