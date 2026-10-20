import { PDFDocument, StandardFonts } from 'pdf-lib'
import { describe, expect, it, vi } from 'vitest'

// countPdfPages dùng pdf.js (cần worker); splitPdf chỉ dùng pdf-lib.
vi.mock('pdfjs-dist', () => ({ getDocument: vi.fn(), GlobalWorkerOptions: {} }))
vi.mock('pdfjs-dist/build/pdf.worker.min.mjs?url', () => ({ default: '' }))

const { PdfSplitUnsupportedError, splitPdf } = await import(
  '../src/pdf/splitPdf'
)

/** Trang n (đếm từ 1) rộng 100 + n điểm và có chữ "Trang n". */
async function mergedPdf(pageCount: number) {
  const doc = await PDFDocument.create()
  const font = await doc.embedFont(StandardFonts.Helvetica)
  for (let n = 1; n <= pageCount; n += 1) {
    const page = doc.addPage([100 + n, 200])
    page.drawText(`Trang ${n}`, { x: 10, y: 100, size: 12, font })
  }
  return doc
}

async function asFile(doc: PDFDocument, name: string) {
  const bytes = await doc.save()
  return new File([bytes as BlobPart], name, { type: 'application/pdf' })
}

async function pageWidths(file: File) {
  const doc = await PDFDocument.load(await file.arrayBuffer())
  return doc.getPages().map((page) => page.getWidth())
}

describe('splitPdf', () => {
  it('cuts each range into its own file, pages in order', async () => {
    const source = await asFile(await mergedPdf(8), 'Hop dong tron.PDF')

    const parts = await splitPdf(source, [
      { pageStart: 1, pageEnd: 3 },
      { pageStart: 4, pageEnd: 6 },
      { pageStart: 7, pageEnd: 8 },
    ])

    expect(parts.map((part) => part.name)).toEqual([
      'Hop dong tron-p1-3.pdf',
      'Hop dong tron-p4-6.pdf',
      'Hop dong tron-p7-8.pdf',
    ])
    expect(parts.every((part) => part.type === 'application/pdf')).toBe(true)
    expect(await pageWidths(parts[0])).toEqual([101, 102, 103])
    expect(await pageWidths(parts[1])).toEqual([104, 105, 106])
    expect(await pageWidths(parts[2])).toEqual([107, 108])
  })

  it('keeps a one-page part', async () => {
    const source = await asFile(await mergedPdf(3), 'a.pdf')

    const parts = await splitPdf(source, [
      { pageStart: 1, pageEnd: 1 },
      { pageStart: 2, pageEnd: 3 },
    ])

    expect(await pageWidths(parts[0])).toEqual([101])
    expect(await pageWidths(parts[1])).toEqual([102, 103])
  })

  it('reports an encrypted PDF as one the browser cannot cut', async () => {
    // PDF chỉ khoá in/sao chép vẫn có /Encrypt trong trailer: pdf-lib từ chối.
    const doc = await mergedPdf(3)
    doc.context.trailerInfo.Encrypt = doc.context.obj({
      Filter: 'Standard',
      V: 2,
      R: 3,
    })
    const source = await asFile(doc, 'khoa-in.pdf')

    const failure = await splitPdf(source, [
      { pageStart: 1, pageEnd: 1 },
      { pageStart: 2, pageEnd: 3 },
    ]).catch((cause: unknown) => cause)

    expect(failure).toBeInstanceOf(PdfSplitUnsupportedError)
    expect((failure as Error).message).toContain('khoa-in.pdf')
  })

  it('reports a file that is not a PDF the same way', async () => {
    const source = new File(['not a pdf'], 'hong.pdf', {
      type: 'application/pdf',
    })

    await expect(
      splitPdf(source, [{ pageStart: 1, pageEnd: 1 }]),
    ).rejects.toBeInstanceOf(PdfSplitUnsupportedError)
  })
})
