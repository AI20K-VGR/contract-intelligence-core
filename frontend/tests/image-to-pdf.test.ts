import { describe, expect, it } from 'vitest'
import {
  asUploadPdf,
  fitSize,
  isImageFile,
  isPdfFile,
  isUploadable,
  pdfNameFor,
} from '../src/pdf/imageToPdf'
import { jpegPdf } from '../src/pdf/jpegPdf'

function file(name: string, type = '') {
  return new File([new Uint8Array([1, 2, 3])], name, { type })
}

describe('image upload filters', () => {
  it('accepts PDF and common image formats by type or extension', () => {
    expect(isPdfFile(file('hd.pdf'))).toBe(true)
    expect(isImageFile(file('scan.JPG'))).toBe(true)
    expect(isImageFile(file('anh', 'image/png'))).toBe(true)
    expect(isUploadable(file('trang.webp'))).toBe(true)
    expect(isUploadable(file('hd.docx'))).toBe(false)
    expect(isUploadable(file('anh.heic', 'image/heic'))).toBe(false)
  })

  it('renames an image to a .pdf filename', () => {
    expect(pdfNameFor('Hop dong trang 1.jpeg')).toBe('Hop dong trang 1.pdf')
    expect(pdfNameFor('.png')).toBe('.png.pdf')
    expect(pdfNameFor('scan')).toBe('scan.pdf')
  })

  it('caps the long side without upscaling small images', () => {
    expect(fitSize(7016, 4960, 3508)).toEqual({ width: 3508, height: 2480 })
    expect(fitSize(800, 1200, 3508)).toEqual({ width: 800, height: 1200 })
  })

  it('passes PDF files through unchanged', async () => {
    const pdf = file('hd.pdf', 'application/pdf')
    expect(await asUploadPdf(pdf)).toBe(pdf)
  })
})

describe('jpegPdf', () => {
  it('writes a single-page PDF whose startxref points at the xref table', async () => {
    const blob = jpegPdf(new Uint8Array([0xff, 0xd8, 0xff, 0xd9]), 595, 842, 10, 14)
    const bytes = new Uint8Array(await blob.arrayBuffer())
    const text = new TextDecoder('latin1').decode(bytes)
    expect(text.startsWith('%PDF-1.4')).toBe(true)
    expect(text).toContain('/MediaBox [0 0 595 842]')
    expect(text).toContain('/Width 10 /Height 14')
    const xrefAt = Number(text.match(/startxref\n(\d+)/)?.[1])
    expect(text.slice(xrefAt, xrefAt + 4)).toBe('xref')
  })
})
