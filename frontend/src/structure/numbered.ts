import { cleanLines } from './lines'
import { isHeadingKind, parseMarker } from './markers'
import { TreeBuilder } from './tree'
import type { ClauseNode, ClauseRegion, OcrLine } from './types'

function lineRegion(line: OcrLine): ClauseRegion | null {
  if (!line.bbox) return null
  return { pageNo: line.pageNo, bbox: line.bbox }
}

const TITLE_NEXT_LINE_MAX = 100

/**
 * Tài liệu có Điều / Khoản / Điểm.
 *
 * Mỗi dòng OCR đi qua parseMarker(). Dòng có ký hiệu mở nút mới ở level của
 * ký hiệu đó; dòng không có ký hiệu nối vào nút đang mở. Tiêu đề Điều nằm ở
 * dòng kế ("Điều 1." rồi xuống dòng "ĐỐI TƯỢNG HỢP ĐỒNG") được ghép lại.
 */
export function buildNumberedTree(input: OcrLine[]): ClauseNode[] {
  const lines = cleanLines(input)
  const builder = new TreeBuilder()

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const marker = parseMarker(line.text)
    if (!marker) {
      builder.append(line.text, line.pageNo, lineRegion(line))
      continue
    }

    let title: string | null = null
    let text = marker.rest
    const regions = [lineRegion(line)].filter(
      (region): region is ClauseRegion => region !== null,
    )
    if (isHeadingKind(marker.kind)) {
      if (marker.rest) {
        title = marker.rest
      } else {
        const next = lines[index + 1]
        if (
          next &&
          next.pageNo === line.pageNo &&
          next.text.trim().length <= TITLE_NEXT_LINE_MAX &&
          !parseMarker(next.text)
        ) {
          title = next.text.trim()
          text = title
          const nextRegion = lineRegion(next)
          if (nextRegion) regions.push(nextRegion)
          index += 1
        }
      }
    }

    builder.open({
      id: `n-${line.pageNo}-${line.lineNo}`,
      level: marker.level,
      nodeType: marker.kind,
      label: marker.raw,
      number: marker.number,
      title,
      text,
      pageNo: line.pageNo,
      regions,
    })
  }

  return builder.build()
}
