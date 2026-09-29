import { jpegPdf } from './jpegPdf'

// Ảnh chụp/scan hợp đồng được gói thành PDF một trang trước khi tải lên, để
// backend, AI1 (OCR trang scan) và trình xem PDF dùng nguyên luồng hiện có.

const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp']

export const UPLOAD_ACCEPT = [
  'application/pdf',
  '.pdf',
  ...IMAGE_TYPES,
  ...IMAGE_EXTENSIONS,
].join(',')

// Khổ A4 dọc tính theo point (1/72 inch).
const A4_WIDTH_PT = 595
// Cạnh dài tối đa của ảnh nhúng: A4 ở 300 DPI, đủ nét cho OCR mà không phình file.
const MAX_LONG_SIDE_PX = 3508
const JPEG_QUALITY = 0.92

function extensionOf(name: string) {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

export function isPdfFile(file: File) {
  return file.type === 'application/pdf' || extensionOf(file.name) === '.pdf'
}

export function isImageFile(file: File) {
  return (
    IMAGE_TYPES.includes(file.type) ||
    IMAGE_EXTENSIONS.includes(extensionOf(file.name))
  )
}

export function isUploadable(file: File) {
  return isPdfFile(file) || isImageFile(file)
}

export function pdfNameFor(name: string) {
  const dot = name.lastIndexOf('.')
  const base = (dot > 0 ? name.slice(0, dot) : name).trim() || 'tai-lieu'
  return `${base}.pdf`
}

export function fitSize(width: number, height: number, maxLongSide: number) {
  const scale = Math.min(1, maxLongSide / Math.max(width, height))
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  }
}

async function decode(file: File): Promise<CanvasImageSource & { width: number; height: number }> {
  if (typeof createImageBitmap === 'function') {
    // from-image: xoay theo EXIF để ảnh chụp điện thoại không bị nằm ngang.
    return createImageBitmap(file, { imageOrientation: 'from-image' })
  }
  const url = URL.createObjectURL(file)
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    return image
  } finally {
    URL.revokeObjectURL(url)
  }
}

export async function imageToPdf(file: File): Promise<File> {
  let source: Awaited<ReturnType<typeof decode>>
  try {
    source = await decode(file)
  } catch {
    throw new Error(`Không đọc được ảnh "${file.name}". Chỉ nhận JPG, PNG, WebP, BMP.`)
  }
  const { width, height } = fitSize(source.width, source.height, MAX_LONG_SIDE_PX)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Trình duyệt không hỗ trợ chuyển ảnh sang PDF.')
  // JPEG không có kênh alpha: nền trắng thay cho vùng trong suốt của PNG.
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, width, height)
  ctx.drawImage(source, 0, 0, width, height)
  if ('close' in source && typeof source.close === 'function') source.close()

  const jpeg = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) =>
        blob
          ? resolve(blob)
          : reject(new Error(`Không chuyển được ảnh "${file.name}" sang PDF.`)),
      'image/jpeg',
      JPEG_QUALITY,
    )
  })
  const pageHeight = Math.round((A4_WIDTH_PT * height) / width)
  const pdf = jpegPdf(
    new Uint8Array(await jpeg.arrayBuffer()),
    A4_WIDTH_PT,
    pageHeight,
    width,
    height,
  )
  return new File([pdf], pdfNameFor(file.name), {
    type: 'application/pdf',
    lastModified: file.lastModified,
  })
}

// PDF giữ nguyên; ảnh được gói thành PDF một trang.
export async function asUploadPdf(file: File): Promise<File> {
  return isImageFile(file) && !isPdfFile(file) ? imageToPdf(file) : file
}
