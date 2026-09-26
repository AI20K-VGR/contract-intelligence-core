import type { ClauseRegion } from '../api/structure'
import type { OcrLine } from './types'

/** Gom chữ để so câu trích với dòng OCR, bỏ dấu câu và khoảng trắng thừa. */
export function squashQuote(text: string) {
  return text
    .normalize('NFC')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Khoanh các dòng OCR nằm trong câu trích.
 * Nếu biết trang điều khoản thì ưu tiên trang đó; không thì lấy trang có nhiều dòng khớp nhất.
 */
export function boxesForQuote(
  lines: OcrLine[],
  quote: string,
  pageHint: number | null = null,
): ClauseRegion[] {
  const needle = squashQuote(quote)
  if (needle.length < 8) return []
  const hits = lines.filter((line) => {
    if (!line.bbox) return false
    const hay = squashQuote(line.text)
    return hay.length >= 8 && needle.includes(hay)
  })
  if (hits.length === 0) return []
  const hinted =
    pageHint && pageHint > 0
      ? hits.filter((line) => Math.abs(line.pageNo - pageHint) <= 1)
      : []
  const pool = hinted.length > 0 ? hinted : densestPages(hits)
  return pool.flatMap((line) =>
    line.bbox ? [{ pageNo: line.pageNo, bbox: line.bbox }] : [],
  )
}

function densestPages(lines: OcrLine[]) {
  const counts = new Map<number, number>()
  for (const line of lines) {
    counts.set(line.pageNo, (counts.get(line.pageNo) ?? 0) + 1)
  }
  let bestPage = lines[0]?.pageNo ?? 1
  let bestCount = 0
  for (const [page, count] of counts) {
    if (count > bestCount) {
      bestPage = page
      bestCount = count
    }
  }
  return lines.filter((line) => Math.abs(line.pageNo - bestPage) <= 1)
}
