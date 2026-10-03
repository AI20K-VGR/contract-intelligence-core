import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadDocumentLines } from '../src/api/structure'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function urlOf(input: Parameters<typeof fetch>[0]) {
  return typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('loadDocumentLines', () => {
  it('loads every page in one request, ordered by page then line', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      json({
        data: [
          {
            page_no: 2,
            width_pt: 600,
            height_pt: 800,
            ocr_lines: [{ id: 'l3', line_no: 1, text: 'Điều 2', bbox: [0, 0, 300, 40] }],
          },
          {
            page_no: 1,
            width_pt: 600,
            height_pt: 800,
            ocr_lines: [
              { id: 'l1', line_no: 1, text: 'Điều 1', bbox: null },
              { id: 'l2', line_no: 2, text: '   ', bbox: null },
            ],
          },
        ],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const lines = await loadDocumentLines('doc-1')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(urlOf(fetchMock.mock.calls[0][0])).toContain('/api/v1/documents/doc-1/lines')
    expect(lines.map((line) => [line.pageNo, line.text])).toEqual([
      [1, 'Điều 1'],
      [2, 'Điều 2'],
    ])
    expect(lines[1]).toMatchObject({ pageWidth: 600, pageHeight: 800 })
  })

  it('falls back to one request per page when the backend has no bulk endpoint', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = urlOf(input)
      if (url.endsWith('/documents/doc-1/lines')) return json({ detail: 'Not Found' }, 404)
      if (url.endsWith('/documents/doc-1/pages')) {
        return json({ data: [{ id: 'pg-1', page_no: 1, width_pt: 600, height_pt: 800 }] })
      }
      if (url.endsWith('/pages/pg-1')) {
        return json({ data: { ocr_lines: [{ id: 'l1', line_no: 1, text: 'Điều 1' }] } })
      }
      return json({}, 500)
    })
    vi.stubGlobal('fetch', fetchMock)

    const lines = await loadDocumentLines('doc-1')

    expect(lines.map((line) => line.id)).toEqual(['l1'])
  })

  it('does not fall back on other errors', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(json({}, 500))
    vi.stubGlobal('fetch', fetchMock)

    await expect(loadDocumentLines('doc-1')).rejects.toMatchObject({ status: 500 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
