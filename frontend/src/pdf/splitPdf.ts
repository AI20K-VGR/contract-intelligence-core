import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

GlobalWorkerOptions.workerSrc = workerUrl

// File trộn hợp đồng và phụ lục được cắt ngay trên trình duyệt: mỗi phần tải
// lên như một tệp riêng, backend không phải tách nữa.

export type PdfPageRange = { pageStart: number; pageEnd: number }

/**
 * pdf-lib không mở được file này. Hay gặp nhất là PDF chỉ khoá in/sao chép
 * (owner password, không có mật khẩu mở): pdf-lib từ chối mọi PDF mã hoá, còn
 * backend đọc được. Khi đó tải nguyên file lên và để backend tách.
 */
export class PdfSplitUnsupportedError extends Error {
  constructor(filename: string, options?: { cause?: unknown }) {
    super(`Trình duyệt không tách được "${filename}".`, options)
    this.name = 'PdfSplitUnsupportedError'
  }
}

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
  } catch (cause) {
    throw new PdfSplitUnsupportedError(file.name, { cause })
  }
  const base = file.name.replace(/\.pdf$/i, '')
  // Lần lượt từng phần: file scan vài chục MB, giữ mọi phần cùng lúc thì tab
  // tốn bộ nhớ gấp nhiều lần.
  const files: File[] = []
  for (const { pageStart, pageEnd } of ranges) {
    const out = await PDFDocument.create()
    const indices = Array.from(
      { length: pageEnd - pageStart + 1 },
      (_, index) => pageStart - 1 + index,
    )
    for (const page of await out.copyPages(source, indices)) {
      out.addPage(page)
    }
    const bytes = await out.save()
    files.push(
      new File(
        [new Blob([bytes as BlobPart], { type: 'application/pdf' })],
        `${base}-p${pageStart}-${pageEnd}.pdf`,
        { type: 'application/pdf' },
      ),
    )
  }
  return files
}
