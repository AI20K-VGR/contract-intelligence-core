// PDF một trang chứa đúng một ảnh JPEG (DCTDecode), đủ để pdf.js và PyMuPDF
// đọc như một trang scan. Không phụ thuộc thư viện ngoài.
export function jpegPdf(
  jpeg: Uint8Array,
  pageWidth: number,
  pageHeight: number,
  imageWidth: number,
  imageHeight: number,
) {
  const encoder = new TextEncoder()
  const parts: Uint8Array[] = []
  let cursor = 0
  const add = (bytes: Uint8Array) => {
    parts.push(bytes)
    cursor += bytes.length
  }
  const addText = (value: string) => add(encoder.encode(value))
  addText('%PDF-1.4\n')
  const xref = [0, 0, 0, 0, 0, 0]
  const content = `q\n${pageWidth} 0 0 ${pageHeight} 0 0 cm\n/Im0 Do\nQ\n`
  const objects = [
    '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
    '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
    `3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Contents 4 0 R /Resources << /XObject << /Im0 5 0 R >> >> >>\nendobj\n`,
    `4 0 obj\n<< /Length ${encoder.encode(content).length} >>\nstream\n${content}endstream\nendobj\n`,
  ]
  objects.forEach((body, index) => {
    xref[index + 1] = cursor
    addText(body)
  })
  xref[5] = cursor
  addText(
    `5 0 obj\n<< /Type /XObject /Subtype /Image /Width ${imageWidth} /Height ${imageHeight} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`,
  )
  add(jpeg)
  addText('\nendstream\nendobj\n')
  const xrefAt = cursor
  let table = 'xref\n0 6\n0000000000 65535 f \n'
  for (let index = 1; index <= 5; index += 1) {
    table += `${String(xref[index]).padStart(10, '0')} 00000 n \n`
  }
  addText(table)
  addText(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF`)
  const out = new Uint8Array(cursor)
  let offset = 0
  for (const part of parts) {
    out.set(part, offset)
    offset += part.length
  }
  return new Blob([out], { type: 'application/pdf' })
}
