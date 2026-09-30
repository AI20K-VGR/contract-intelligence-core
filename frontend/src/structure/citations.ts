import type { ClauseNode } from '../api/structure'

/**
 * Số trích dẫn: hết một cấp (từ trên xuống) rồi mới sang cấp sâu hơn.
 */
export function citationNumbers(nodes: ClauseNode[]) {
  const order = new Map<string, number>()
  let cursor = 1
  let level = nodes
  while (level.length > 0) {
    const next: ClauseNode[] = []
    for (const node of level) {
      order.set(node.id, cursor)
      cursor += 1
      next.push(...node.children)
    }
    level = next
  }
  return order
}

export function findClause(nodes: ClauseNode[], id: string): ClauseNode | null {
  for (const node of nodes) {
    if (node.id === id) return node
    const child = findClause(node.children, id)
    if (child) return child
  }
  return null
}

function squash(text: string) {
  return text.replace(/\s+/g, ' ').trim().toLowerCase()
}

function walk(nodes: ClauseNode[], visit: (node: ClauseNode) => void) {
  for (const node of nodes) {
    visit(node)
    walk(node.children, visit)
  }
}

/**
 * Tìm nút trong cây (dựng trên trình duyệt) khớp với câu AI2 trích.
 * AI2 dùng node_id của cây riêng, nên đối chiếu bằng chữ và trang:
 * ưu tiên nút nhỏ nhất chứa trọn câu trích, cùng trang nếu biết trang.
 */
export function findClauseByQuote(
  nodes: ClauseNode[],
  quote: string,
  pageNo: number | null,
): ClauseNode | null {
  const needle = squash(quote)
  if (needle.length < 4) return null
  let best: ClauseNode | null = null
  let bestScore = Number.POSITIVE_INFINITY
  walk(nodes, (node) => {
    if (pageNo !== null && (node.pageStart > pageNo || node.pageEnd < pageNo))
      return
    const hay = squash(`${node.label} ${node.title ?? ''} ${node.text}`)
    if (!hay.includes(needle)) return
    // Nút ngắn hơn là nút cụ thể hơn; cùng độ dài thì lấy nút gặp trước.
    const score = hay.length
    if (score < bestScore) {
      best = node
      bestScore = score
    }
  })
  if (best) return best
  // Câu trích dài có thể bị OCR ngắt khác; thử khớp nửa đầu câu.
  if (needle.length > 40) {
    return findClauseByQuote(
      nodes,
      quote.slice(0, Math.floor(quote.length / 2)),
      pageNo,
    )
  }
  return null
}

/** Một số trích dẫn của cây, gắn với câu AI2 đã khớp nút. */
export type SearchCite = {
  id: string
  n: number
  quote: string
}

function hasMatchedDescendant(node: ClauseNode, ids: ReadonlySet<string>): boolean {
  return node.children.some(
    (child) => ids.has(child.id) || hasMatchedDescendant(child, ids),
  )
}

/** Nút lá (cụ thể nhất) có chữ nằm trong đoạn AI2. */
function nodesInsideText(nodes: ClauseNode[], blob: string): ClauseNode[] {
  const hay = squash(blob)
  if (hay.length < 8) return []
  const found: ClauseNode[] = []
  walk(nodes, (node) => {
    const body = squash(node.text)
    const label = squash(`${node.label} ${node.title ?? ''}`)
    const needle = body.length >= 12 ? body : label.length >= 6 ? label : ''
    if (!needle || !hay.includes(needle)) return
    found.push(node)
  })
  const ids = new Set(found.map((node) => node.id))
  return found.filter((node) => !hasMatchedDescendant(node, ids))
}

/**
 * Đối soát AI2 bằng đúng số của sơ đồ.
 * Evidence AI2 thường dài hơn một nút, nên lấy mọi nút có chữ nằm trong
 * câu trả lời hoặc trong đoạn trích, rồi dùng số `citationNumbers` của nút đó.
 */
export function searchCites(
  nodes: ClauseNode[],
  hits: { text: string; pageNo: number | null }[],
  numbers: ReadonlyMap<string, number>,
  answer = '',
): SearchCite[] {
  const blobs = [
    ...hits.map((hit) => hit.text),
    answer,
  ].filter((blob) => blob.trim().length >= 8)
  const seen = new Set<string>()
  const cites: SearchCite[] = []
  for (const blob of blobs) {
    for (const clause of nodesInsideText(nodes, blob)) {
      if (seen.has(clause.id)) continue
      const n = numbers.get(clause.id)
      if (!n) continue
      seen.add(clause.id)
      const body = squash(clause.text)
      cites.push({
        id: clause.id,
        n,
        quote: body.length >= 12 ? body : squash(`${clause.label} ${clause.title ?? ''}`),
      })
    }
  }
  return cites
}
