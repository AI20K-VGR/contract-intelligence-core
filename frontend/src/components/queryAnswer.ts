import type { QueryHistoryCitation } from '../api/queries'

/** Dòng bắt đầu một mục mới: tiêu đề Điều/Chương, khoản đánh số, gạch đầu dòng. */
const ITEM_START = /^(\d+(\.\d+)*\.?\s|(điều|chương|mục|phụ lục)\s|[-•*]\s)/i

export type AnswerBlock = {
  kind: 'heading' | 'item' | 'text'
  no?: string
  text: string
}

export type NumberedCitation = { citation: QueryHistoryCitation; n: number }

/** Số khoản đầu câu trích: "5.2. ", "3 ". Dòng nối của khoản không có. */
const CLAUSE_NUMBER = /^\d+(\.\d+)*\.?\s*/

/**
 * Mức căn cứ của câu trả lời (`state` của AI2, BE-AI2-PROCESSING-CONTRACT):
 * chỉ gắn nhãn khi không bình thường, để người đọc biết câu nào phải tự kiểm.
 * `ANSWERED` (có căn cứ) không gắn nhãn; mã lạ cũng không hiện.
 */
export const ANSWER_STATE_LABELS: Record<
  string,
  { label: string; tone: 'warn' | 'neutral' }
> = {
  // Gồm cả khi AI quá 15 giây, chỉ trả đoạn trích chứ không kịp tổng hợp.
  NEEDS_REVIEW: { label: 'Chưa đủ căn cứ, cần kiểm lại', tone: 'warn' },
  INSUFFICIENT_EVIDENCE: { label: 'Thiếu căn cứ trong hồ sơ', tone: 'warn' },
  BLOCKED: { label: 'Không được trả lời', tone: 'neutral' },
}

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
 *
 * AI2 trả một trích dẫn cho mỗi dòng chữ, theo thứ tự, nên một khoản dài hai
 * dòng có hai trích dẫn cùng mở một chỗ. Chỉ gộp dòng nối của khoản: trích dẫn
 * ngay sau một trích dẫn cùng mục, cùng tài liệu, cùng trang, và câu trích không
 * bắt đầu bằng số khoản. Khoản mới ("5.2. …") luôn có số riêng, kể cả khi cùng
 * trang với khoản trước; hợp đồng và phụ lục vẫn tách riêng. Ngoài ra chỉ bỏ
 * trích dẫn trùng hẳn (cùng mục hoặc cùng ngoài mục, tài liệu, trang, câu trích).
 * `n` đánh liên tục từ 1 theo thứ tự xuất hiện, sau khi đã gộp.
 */
export function citesByBlock(
  blocks: AnswerBlock[],
  citations: QueryHistoryCitation[],
) {
  const placed = new Map<number, NumberedCitation[]>()
  const unplaced: NumberedCitation[] = []
  const seen = new Set<string>()
  // Trích dẫn liền trước (kể cả đã gộp): dòng nối chỉ gộp vào khoản ngay trước nó.
  let previous: { at: number; source: string; page: number | '' } | null = null
  let n = 0
  for (const citation of citations) {
    const quote = norm(citation.quote)
    const key = quote.replace(CLAUSE_NUMBER, '').slice(0, 40)
    const at = key
      ? blocks.findIndex((block) =>
          norm(`${block.no ?? ''} ${block.text}`).includes(key),
        )
      : -1
    const source = citation.documentId ?? ''
    const page = citation.pageNo ?? ''
    const continuation =
      at >= 0 &&
      source !== '' &&
      previous !== null &&
      previous.at === at &&
      previous.source === source &&
      previous.page === page &&
      !CLAUSE_NUMBER.test(quote)
    previous = { at, source, page }
    const identity = `${at}|${source}|${page}|${quote}`
    if (continuation || seen.has(identity)) continue
    seen.add(identity)
    n += 1
    const entry = { citation, n }
    if (at < 0) {
      unplaced.push(entry)
      continue
    }
    placed.set(at, [...(placed.get(at) ?? []), entry])
  }
  return { placed, unplaced }
}
