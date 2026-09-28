import type { OcrLine } from './types'

const PAGE_NUMBER_RE =
  /^(?:trang|page|tr\.?)?\s*[-–]?\s*\d{1,3}\s*(?:(?:\/|of|trên)\s*\d{1,3})?\s*[-–]?$/i

const DIGIT_RE = /\d+/g

// Khối chữ ký cuối văn bản: không phải nội dung cấu trúc.
const SIGNATURE_RE =
  /^(?:\(?\s*(?:ký|kí)\b|đại\s+diện\b|người\s+đại\s+diện\b|chức\s+vụ\s*:?\s*$|họ\s+(?:và\s+)?tên\s*:?\s*$|(?:t\/m|tm\.?|kt\.?)\s+)/iu
const SIGNATURE_MAX_LENGTH = 40

function repeatKey(text: string) {
  return text.replace(/\s+/g, ' ').replace(DIGIT_RE, '#').trim().toLowerCase()
}

function inEdgeBand(line: OcrLine) {
  if (!line.bbox) return true
  const [, y1, , y2] = line.bbox
  return y1 < 0.12 || y2 > 0.88
}

/**
 * Sắp theo thứ tự đọc và bỏ nhiễu: dòng trống, số trang, header/footer lặp
 * trên nhiều trang. Không đổi nội dung dòng nào.
 */
export function cleanLines(input: OcrLine[]): OcrLine[] {
  const lines = input
    .filter((line) => line.text.trim().length > 0)
    .sort((a, b) => a.pageNo - b.pageNo || a.lineNo - b.lineNo)

  const pageCount = new Set(lines.map((line) => line.pageNo)).size
  const pagesByKey = new Map<string, Set<number>>()
  if (pageCount >= 3) {
    for (const line of lines) {
      if (!inEdgeBand(line)) continue
      const key = repeatKey(line.text)
      if (key.length < 3) continue
      const pages = pagesByKey.get(key) ?? new Set<number>()
      pages.add(line.pageNo)
      pagesByKey.set(key, pages)
    }
  }
  const repeatThreshold = Math.max(2, Math.ceil(pageCount * 0.5))

  return lines.filter((line) => {
    const text = line.text.trim()
    if (PAGE_NUMBER_RE.test(text)) return false
    if (text.length <= SIGNATURE_MAX_LENGTH && SIGNATURE_RE.test(text)) {
      return false
    }
    if (pageCount >= 3 && inEdgeBand(line)) {
      const pages = pagesByKey.get(repeatKey(text))
      if (pages && pages.size >= repeatThreshold) return false
    }
    return true
  })
}

export function lineHeightPt(line: OcrLine) {
  if (!line.bbox) return null
  const height = (line.bbox[3] - line.bbox[1]) * line.pageHeight
  return height > 0 ? height : null
}

export function median(values: number[]) {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid]
}
