import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

GlobalWorkerOptions.workerSrc = workerUrl

// File trộn hợp đồng và phụ lục được cắt ngay trên trình duyệt: mỗi phần tải
// lên như một tệp riêng, backend không phải tách nữa.

export type PdfPageRange = { pageStart: number; pageEnd: number }

export async function countPdfPages(file: File) {
  const task = getDocument({ data: new Uint8Array(await file.arrayBuffer()) })
  try {
    return (await task.promise).numPages
  } finally {
    void task.destroy()
  }
}

/** Mỗi khoảng trang (đếm từ 1) thành một PDF riêng, tên `<gốc>-p<đầu>-<cuối>.pdf`. */
export async function splitPdf(
  file: File,
  ranges: PdfPageRange[],
): Promise<File[]> {
  const { PDFDocument } = await import('pdf-lib')
  let source: Awaited<ReturnType<typeof PDFDocument.load>>
  try {
    source = await PDFDocument.load(await file.arrayBuffer())
  } catch {
    throw new Error(
      `Không tách được "${file.name}" (file có mật khẩu hoặc bị lỗi). Hãy tách sẵn thành từng tệp rồi tải lên.`,
    )
  }
  const base = file.name.replace(/\.pdf$/i, '')
  return Promise.all(
    ranges.map(async ({ pageStart, pageEnd }) => {
      const out = await PDFDocument.create()
      const indices = Array.from(
        { length: pageEnd - pageStart + 1 },
        (_, index) => pageStart - 1 + index,
      )
      for (const page of await out.copyPages(source, indices)) {
        out.addPage(page)
      }
      const bytes = await out.save()
      return new File(
        [new Blob([bytes as BlobPart], { type: 'application/pdf' })],
        `${base}-p${pageStart}-${pageEnd}.pdf`,
        { type: 'application/pdf' },
      )
    }),
  )
}
