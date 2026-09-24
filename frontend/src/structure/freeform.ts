import { cleanLines, lineHeightPt, median } from './lines'
import { TreeBuilder } from './tree'
import type { ClauseNode, ClauseRegion, OcrLine } from './types'

function lineRegion(line: OcrLine): ClauseRegion | null {
  if (!line.bbox) return null
  return { pageNo: line.pageNo, bbox: line.bbox }
}

const HEADING_MAX_LENGTH = 90
const HEADING_MIN_SCORE = 4
const SIZE_CLUSTER_TOLERANCE = 0.1

const KEYWORD_RE =
  /^(Phần|Chương|Mục|Điều|Phụ\s*lục|Article|Section|Chapter|Part|Annex|Appendix)\b/iu
const SENTENCE_END_RE = /[.,;]$/
const LOWER_START_RE = /^\p{Ll}/u
const LETTER_RE = /\p{L}/gu
const UPPER_RE = /\p{Lu}/gu
const DIGIT_RE = /\d/g

type Scored = {
  line: OcrLine
  heading: boolean
  /** Khóa xếp cấp: cỡ chữ tương đối + thưởng viết hoa / canh giữa. */
  sizeKey: number
  upper: boolean
  keyword: boolean
}

function count(text: string, re: RegExp) {
  return (text.match(re) ?? []).length
}

/**
 * Tài liệu tự do, không đánh số.
 *
 * Không đọc nghĩa. Mỗi dòng được chấm điểm "giống tiêu đề" theo hình dạng:
 * cỡ chữ so với cỡ chữ phổ biến, viết hoa, ngắn, không kết thúc bằng dấu câu,
 * khoảng trống phía trên lớn, canh giữa, bắt đầu bằng từ khóa mục. Dòng đạt
 * ngưỡng là tiêu đề. Cấp của tiêu đề suy từ cỡ chữ: gom các cỡ gần nhau thành
 * một cấp, cỡ lớn nhất là cấp cao nhất. Số cấp không giới hạn.
 */
export function buildFreeformTree(input: OcrLine[]): ClauseNode[] {
  const lines = cleanLines(input)
  if (lines.length === 0) return []

  const heights = lines.map(lineHeightPt)
  const bodyHeights = heights.filter(
    (height, index): height is number =>
      height !== null && lines[index].text.trim().length >= 25,
  )
  const allHeights = heights.filter(
    (height): height is number => height !== null,
  )
  const bodyHeight = median(bodyHeights.length >= 5 ? bodyHeights : allHeights)

  const gaps: (number | null)[] = lines.map((line, index) => {
    const prev = lines[index - 1]
    if (!prev || prev.pageNo !== line.pageNo || !prev.bbox || !line.bbox) {
      return null
    }
    return (line.bbox[1] - prev.bbox[3]) * line.pageHeight
  })
  const bodyGap = median(
    gaps.filter((gap): gap is number => gap !== null && gap > 0),
  )

  const scored: Scored[] = lines.map((line, index) => {
    const text = line.text.trim()
    const letters = count(text, LETTER_RE)
    const upperLetters = count(text, UPPER_RE)
    const digits = count(text, DIGIT_RE)
    const height = heights[index]
    const ratio = height !== null && bodyHeight > 0 ? height / bodyHeight : null
    const gapAbove = gaps[index]
    const gapBelow = gaps[index + 1] ?? null

    const upper = letters >= 3 && upperLetters / letters >= 0.8
    const keyword = KEYWORD_RE.test(text)
    const short = text.length <= HEADING_MAX_LENGTH
    const endsSentence = SENTENCE_END_RE.test(text)
    const centered =
      line.bbox !== null &&
      Math.abs((line.bbox[0] + line.bbox[2]) / 2 - 0.5) < 0.08 &&
      line.bbox[2] - line.bbox[0] < 0.6

    let score = 0
    // Cỡ chữ lớn hơn thân bài: tín hiệu mạnh nhất.
    if (ratio !== null) {
      if (ratio >= 1.08) score += 1
      if (ratio >= 1.15) score += 1
      if (ratio >= 1.35) score += 1
    }
    if (upper) score += 2
    if (keyword) score += 2
    // Khoảng trống phía trên lớn hơn hẳn khoảng cách dòng thường.
    if (gapAbove !== null && bodyGap > 0 && gapAbove > bodyGap * 1.8) {
      score += 1
    }
    // Tiêu đề tách khỏi đoạn trước (trống trên) nhưng dính với thân bài
    // ngay dưới (trống dưới bình thường). Dòng cuối đoạn thì ngược lại.
    if (
      gapAbove !== null &&
      gapBelow !== null &&
      gapAbove > 0 &&
      gapAbove > gapBelow * 1.5
    ) {
      score += 1
    }
    if (centered) score += 1
    // Ngắn, mở đầu viết hoa, không kết câu: hình dạng của một tiêu đề.
    if (short && !endsSentence && !LOWER_START_RE.test(text)) score += 1
    if (endsSentence) score -= 2
    if (LOWER_START_RE.test(text)) score -= 3
    if (text.length > 0 && digits / text.length > 0.3) score -= 2

    // Không có tọa độ thì mất tín hiệu cỡ chữ và khoảng trống: hạ ngưỡng.
    const minScore = line.bbox ? HEADING_MIN_SCORE : HEADING_MIN_SCORE - 1
    const heading = letters >= 2 && (short || keyword) && score >= minScore

    const sizeKey = (ratio ?? 1) + (upper ? 0.12 : 0) + (centered ? 0.06 : 0)

    return { line, heading, sizeKey, upper, keyword }
  })

  const levelOf = assignLevels(scored.filter((item) => item.heading))

  const builder = new TreeBuilder()
  for (const item of scored) {
    const text = item.line.text.trim()
    const region = lineRegion(item.line)
    if (!item.heading) {
      builder.append(text, item.line.pageNo, region)
      continue
    }
    builder.open({
      id: `h-${item.line.pageNo}-${item.line.lineNo}`,
      level: levelOf.get(item) ?? 0,
      nodeType: 'heading',
      label: text,
      number: null,
      title: text,
      text,
      pageNo: item.line.pageNo,
      regions: region ? [region] : [],
    })
  }

  return unwrapSingleRoot(builder.build())
}

/**
 * Gom tiêu đề theo cỡ chữ. Cỡ lớn nhất là cấp 0. Hai cỡ chênh dưới 10% coi
 * là cùng cấp. Khi OCR không có tọa độ, xếp theo viết hoa + từ khóa.
 */
function assignLevels(headings: Scored[]) {
  const levels = new Map<Scored, number>()
  const hasGeometry = headings.some((item) => item.line.bbox !== null)

  if (!hasGeometry) {
    for (const item of headings) {
      levels.set(item, item.upper && item.keyword ? 0 : item.upper ? 1 : 2)
    }
    return levels
  }

  const keys = [...new Set(headings.map((item) => item.sizeKey))].sort(
    (a, b) => b - a,
  )
  const clusters: number[][] = []
  for (const key of keys) {
    const last = clusters[clusters.length - 1]
    if (last && Math.abs(last[0] - key) / last[0] <= SIZE_CLUSTER_TOLERANCE) {
      last.push(key)
    } else {
      clusters.push([key])
    }
  }
  const levelByKey = new Map<number, number>()
  clusters.forEach((cluster, level) => {
    for (const key of cluster) levelByKey.set(key, level)
  })
  for (const item of headings) {
    levels.set(item, levelByKey.get(item.sizeKey) ?? clusters.length)
  }
  return levels
}

/**
 * Tên tài liệu thường là tiêu đề lớn nhất và ôm hết phần còn lại. Gốc sơ đồ
 * đã hiện tên hồ sơ, nên bỏ lớp bọc này để các mục lớn thành nhánh.
 */
function unwrapSingleRoot(nodes: ClauseNode[]): ClauseNode[] {
  let current = nodes
  while (current.length === 1 && current[0].children.length > 0) {
    current = current[0].children
  }
  return current
}
