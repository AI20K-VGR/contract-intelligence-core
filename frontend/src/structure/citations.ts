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
  documentId?: string | null
  pageNo?: number | null
  lineId?: string | null
  /** Tọa độ citation AI2 trả về, chuẩn hóa 0..1 theo trang. */
  bbox?: [number, number, number, number] | null
}

/** Dựng node tối thiểu để CitationPane dùng chung cho cả tài liệu thân và phụ lục. */
export function citationNode(cite: SearchCite, fallbackIndex = 0): ClauseNode {
  const pageNo = cite.pageNo && cite.pageNo > 0 ? cite.pageNo : 1
  const bbox = cite.bbox
  const hasBbox =
    Array.isArray(bbox) &&
    bbox.length === 4 &&
    bbox.every((value) => Number.isFinite(value)) &&
    bbox[2] > bbox[0] &&
    bbox[3] > bbox[1] &&
    bbox[0] >= 0 &&
    bbox[1] >= 0 &&
    bbox[2] <= 1 &&
    bbox[3] <= 1
  return {
    id: cite.lineId || cite.id || `search-citation-${fallbackIndex}`,
    nodeType: 'line',
    label: 'Citation',
    number: null,
    title: null,
    text: cite.quote,
    pageStart: pageNo,
    pageEnd: pageNo,
    confidence: null,
    regions: hasBbox
      ? [{ pageNo, bbox: bbox as [number, number, number, number] }]
      : [],
    children: [],
  }
}

type CitationTable = {
  pageNo: number
  cells: ReadonlyArray<{
    row: number
    text: string
    bbox: [number, number, number, number] | null
    header: boolean
  }>
}

function compactCitationText(text: string) {
  return squash(text).replace(/[|·,:;()[\]"']/g, '').replace(/\s+/g, '')
}

/** Lấy bbox của dòng bảng khi AI2 chỉ có line text mà OCR không có geometry. */
export function citationTableBbox(
  cite: SearchCite,
  tables: ReadonlyArray<CitationTable>,
): [number, number, number, number] | null {
  const needle = compactCitationText(cite.quote)
  if (needle.length < 8) return null
  let best: [number, number, number, number] | null = null
  let bestScore = 0
  for (const table of tables) {
    if (cite.pageNo !== null && cite.pageNo !== undefined && table.pageNo !== cite.pageNo)
      continue
    const rows = new Map<number, Array<CitationTable['cells'][number]>>()
    for (const cell of table.cells) {
      const row = rows.get(cell.row) ?? []
      row.push(cell)
      rows.set(cell.row, row)
    }
    for (const cells of rows.values()) {
      const nonHeader = cells.filter((cell) => !cell.header && cell.text.trim())
      if (nonHeader.length === 0) continue
      const rowText = compactCitationText(nonHeader.map((cell) => cell.text).join(' '))
      const matching = nonHeader.filter((cell) => {
        const value = compactCitationText(cell.text)
        return value.length >= 4 && (needle.includes(value) || value.includes(needle))
      })
      const rowMatches =
        matching.length >= 2 ||
        (rowText.length >= 8 && (needle.includes(rowText) || rowText.includes(needle)))
      if (!rowMatches) continue
      const boxes = nonHeader
        .map((cell) => cell.bbox)
        .filter(
          (bbox): bbox is [number, number, number, number] =>
            Array.isArray(bbox) &&
            bbox.length === 4 &&
            bbox.every((value) => Number.isFinite(value)) &&
            bbox[2] > bbox[0] &&
            bbox[3] > bbox[1],
        )
      if (boxes.length === 0) continue
      const score = matching.length * 100 + Math.min(rowText.length, 100)
      if (score <= bestScore) continue
      bestScore = score
      best = [
        Math.min(...boxes.map((box) => box[0])),
        Math.min(...boxes.map((box) => box[1])),
        Math.max(...boxes.map((box) => box[2])),
        Math.max(...boxes.map((box) => box[3])),
      ]
    }
  }
  return best
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
  hits: {
    text: string
    pageNo: number | null
    lineId?: string | null
    sourceFileId?: string | null
    bbox?: [number, number, number, number] | null
    citation?: {
      quote?: string | null
      documentId?: string | null
      sourceFileId?: string | null
      lineId?: string | null
      bbox?: [number, number, number, number] | null
    }
  }[],
  numbers: ReadonlyMap<string, number>,
  answer = '',
  sourceDocumentId: string | null = null,
): SearchCite[] {
  const answerText = squash(answer)
  const maxNumber = Math.max(0, ...Array.from(numbers.values()))
  let nextForeignNumber = maxNumber + 1
  const lineNode = (lineId: string | null | undefined) => {
    const match = lineId?.match(/(?:^|:)p(\d+):l(\d+)$/i)
    return match
      ? findClause(nodes, `n-${Number(match[1])}-${Number(match[2])}`)
      : null
  }
  const directNode = (hit: (typeof hits)[number]) => {
    const documentId =
      hit.citation?.documentId ?? hit.citation?.sourceFileId ?? hit.sourceFileId ?? null
    if (sourceDocumentId && documentId && documentId !== sourceDocumentId) return null
    // OCR line ids are more reliable than answer text: the latter may repeat
    // a phrase such as "phụ lục" in another article.  Use the same node id
    // convention as buildNumberedTree when the cited line opened a node.
    const line = lineNode(hit.lineId ?? hit.citation?.lineId)
    if (line) return line
    const quote = hit.citation?.quote || hit.text
    return quote ? findClauseByQuote(nodes, quote, hit.pageNo) : null
  }
  const seen = new Set<string>()
  const cites: SearchCite[] = []
  hits.forEach((hit, index) => {
    const documentId =
      hit.citation?.documentId ?? hit.citation?.sourceFileId ?? hit.sourceFileId ?? null
    const clause = directNode(hit)
    const candidates = [
      hit.citation?.quote,
      hit.text,
      ...(clause ? [clause.text, `${clause.label} ${clause.title ?? ''}`] : []),
    ].filter((value): value is string => Boolean(value && value.trim().length >= 4))
    const quote = candidates.find((value) => answerText.includes(squash(value)))
      ?? candidates[0]
    if (!clause) {
      // The structure page currently loads the contract document only. Keep a
      // foreign-document citation visible, but never map its page/line id onto
      // a body node with the same page number (for example annex p2:l5 → Điều 2).
      if (!sourceDocumentId || !documentId || documentId === sourceDocumentId || !quote) return
      if (!answerText.includes(squash(quote))) return
      const id = `foreign:${documentId}:${hit.lineId ?? hit.citation?.lineId ?? hit.pageNo ?? index}`
      if (seen.has(id)) return
      seen.add(id)
      cites.push({
        id,
        n: nextForeignNumber++,
        quote,
        documentId,
        pageNo: hit.pageNo,
        lineId: hit.lineId ?? hit.citation?.lineId ?? null,
        bbox: hit.bbox ?? hit.citation?.bbox ?? null,
      })
      return
    }
    if (seen.has(clause.id)) return
    const n = numbers.get(clause.id)
    if (!n || !quote) return
    seen.add(clause.id)
    cites.push({
      id: clause.id,
      n,
      quote,
      documentId: hit.citation?.documentId ?? hit.citation?.sourceFileId ?? hit.sourceFileId ?? null,
      pageNo: hit.pageNo,
      lineId: hit.lineId ?? hit.citation?.lineId ?? null,
      bbox: hit.bbox ?? hit.citation?.bbox ?? null,
    })
  })

  // Keep the legacy answer scan only when AI2 returned no mappable citation.
  // It preserves old snapshots while preventing a repeated phrase from an
  // unrelated clause from hijacking a real citation.
  if (cites.length === 0 && (!sourceDocumentId || hits.length === 0)) {
    const blobs = [answer].filter((blob) => blob.trim().length >= 8)
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
  }
  return cites
}
