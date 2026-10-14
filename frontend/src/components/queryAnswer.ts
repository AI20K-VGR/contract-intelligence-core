import type { QueryHistoryCitation } from '../api/queries'

/** Dòng bắt đầu một mục mới: tiêu đề Điều/Chương, khoản đánh số, gạch đầu dòng. */
const ITEM_START = /^(\d+(\.\d+)*\.?\s|(điều|chương|mục|phụ lục)\s|[-•*]\s)/i

export type AnswerBlock = {
  kind: 'heading' | 'item' | 'text'
  no?: string
  text: string
}

export type NumberedCitation = { citation: QueryHistoryCitation; n: number }

export const norm = (text: string) =>
  text.toLowerCase().replace(/\s+/g, ' ').trim()

/**
 * OCR ngắt dòng giữa câu; gộp lại thành từng mục: tiêu đề Điều và từng khoản.
 * "4.1. Nội dung" tách thành số "4.1" và phần chữ để trình bày riêng.
 */
export function answerBlocks(answer: string) {
  const blocks: AnswerBlock[] = []
  for (const raw of answer.split(/\n+/)) {
    const line = raw.trim()
    if (!line) continue
    const last = blocks[blocks.length - 1]
    if (last && !ITEM_START.test(line)) {
      last.text = `${last.text} ${line}`
      continue
    }
    if (/^(điều|chương|mục|phụ lục)\s/i.test(line)) {
      blocks.push({ kind: 'heading', text: line })
      continue
    }
    const numbered = /^(\d+(?:\.\d+)*)\.?\s+(.*)$/.exec(line)
    if (numbered) {
      blocks.push({ kind: 'item', no: numbered[1], text: numbered[2] ?? '' })
      continue
    }
    blocks.push({ kind: 'text', text: line })
  }
  return blocks
}

/**
 * Trích dẫn thuộc mục nào: so phần đầu câu trích (bỏ số khoản) với nội dung mục.
 * Trích dẫn không khớp mục nào, hoặc không có câu trích, vào `unplaced`; không
 * gắn vào mục cuối, để người đọc không hiểu nhầm nó chứng minh cho mục đó.
 * `n` là số thứ tự trong danh sách trích dẫn gốc (bắt đầu từ 1).
 */
export function citesByBlock(
  blocks: AnswerBlock[],
  citations: QueryHistoryCitation[],
) {
  const placed = new Map<number, NumberedCitation[]>()
  const unplaced: NumberedCitation[] = []
  citations.forEach((citation, index) => {
    const entry = { citation, n: index + 1 }
    const key = norm(citation.quote)
      .replace(/^\d+(\.\d+)*\.?\s*/, '')
      .slice(0, 40)
    const at = key
      ? blocks.findIndex((block) =>
          norm(`${block.no ?? ''} ${block.text}`).includes(key),
        )
      : -1
    if (at < 0) {
      unplaced.push(entry)
      return
    }
    placed.set(at, [...(placed.get(at) ?? []), entry])
  })
  return { placed, unplaced }
}
