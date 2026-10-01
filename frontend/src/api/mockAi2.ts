// TẠM THỜI: giả lập câu trả lời AI2 để test giao diện trích dẫn khi backend
// chưa nối được AI2. Bật bằng VITE_MOCK_AI2=true trong .env.local.
// Gỡ bỏ: xóa file này và đoạn `mockAi2Enabled` trong DossierStructurePage.tsx.
import type { OcrLine } from '../structure/types'
import { normalizeAi2SearchResult, type Ai2SearchResult } from './ai2'

export const mockAi2Enabled = import.meta.env.VITE_MOCK_AI2 === 'true'

function words(text: string) {
  return text
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter((word) => word.length >= 2)
}

export async function mockSearchResult(
  dossierId: string,
  documentId: string | null,
  lines: OcrLine[],
  question: string,
): Promise<Ai2SearchResult> {
  await new Promise((resolve) => setTimeout(resolve, 600))
  const terms = new Set(words(question))
  const scored = lines
    .map((line) => ({
      line,
      score: words(line.text).filter((word) => terms.has(word)).length,
    }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)

  if (!documentId || scored.length === 0) {
    return normalizeAi2SearchResult(
      {
        query: question,
        answer: null,
        connected: true,
        review_state: 'INSUFFICIENT_EVIDENCE',
        hits: [],
      },
      dossierId,
    )
  }

  const top = scored[0].line
  return normalizeAi2SearchResult(
    {
      query: question,
      answer: `[MOCK] Theo hợp đồng: ${top.text}`,
      connected: true,
      review_state: 'ANSWERED',
      hits: scored.map(({ line }) => ({
        text: line.text,
        page_no: line.pageNo,
        source_file_id: documentId,
        line_id: line.id,
        bbox: line.bbox,
      })),
    },
    dossierId,
  )
}
