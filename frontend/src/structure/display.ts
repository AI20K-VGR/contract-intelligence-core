import type { ClauseNode } from '../api/structure'

/*
 * Nhãn, màu nhánh và các phép duyệt cây dùng chung cho mọi kiểu xem
 * (sơ đồ tư duy, dàn bài, văn bản, bản đồ trang).
 */

export const typeLabels: Record<string, string> = {
  part: 'Phần',
  chapter: 'Chương',
  section: 'Mục',
  article: 'Điều',
  clause: 'Khoản',
  point: 'Điểm',
  item: 'Ý',
  heading: 'Mục',
  unmarked: 'Đoạn',
  annex: 'Phụ lục',
  preamble: 'Mở đầu',
  signature_block: 'Chữ ký',
}

export type BranchTone = {
  line: string
  bg: string
  bgSoft: string
  border: string
  text: string
}

/** Bảng màu nhánh kiểu Google: mỗi nhánh cấp 1 một màu, cấp sâu nhạt hơn. */
export const branchTones: BranchTone[] = [
  {
    line: '#1a73e8',
    bg: '#d3e3fd',
    bgSoft: '#eaf1fe',
    border: '#a8c7fa',
    text: '#041e49',
  },
  {
    line: '#188038',
    bg: '#c4eed0',
    bgSoft: '#e6f4ea',
    border: '#9ad7ac',
    text: '#072711',
  },
  {
    line: '#e37400',
    bg: '#feefc3',
    bgSoft: '#fef7e0',
    border: '#fbd77f',
    text: '#3d2b00',
  },
  {
    line: '#d93025',
    bg: '#fad2cf',
    bgSoft: '#fce8e6',
    border: '#f4a9a3',
    text: '#410e0b',
  },
  {
    line: '#8430ce',
    bg: '#e9d2fd',
    bgSoft: '#f3e8fd',
    border: '#d0a6f7',
    text: '#2b0a4c',
  },
  {
    line: '#129eaf',
    bg: '#c4eef3',
    bgSoft: '#e0f7fa',
    border: '#8fdce4',
    text: '#003438',
  },
]

export function toneAt(branch: number) {
  return branchTones[
    ((branch % branchTones.length) + branchTones.length) % branchTones.length
  ]
}

export function cleanToken(value: string) {
  return value
    .replace(/^(article|clause|point|unmarked|section|annex)[_\s-]*/i, '')
    .replace(/unnumbered[_\s-]*/i, '')
    .replace(/_/g, ' ')
    .trim()
}

export function shortText(text: string, max: number) {
  const line = text.replace(/\s+/g, ' ').trim()
  if (!line) return ''
  if (line.length <= max) return line
  return `${line.slice(0, max - 1)}…`
}

export function kindOf(node: ClauseNode) {
  return typeLabels[node.nodeType] ?? 'Mục'
}

/** "Điều 3", "Khoản 2.1", "Phụ lục 01"… hoặc rỗng nếu không có số hiệu. */
export function headOf(node: ClauseNode) {
  const kind = kindOf(node)
  const number = cleanToken(node.number ?? '')
  if (!number) return ''
  return number.toLowerCase().startsWith(kind.toLowerCase())
    ? number
    : `${kind} ${number}`
}

/** Tiêu đề riêng của nút (không trùng với nội dung), hoặc rỗng. */
export function titleOf(node: ClauseNode) {
  const title = cleanToken(node.title ?? '')
  const body = node.text.replace(/\s+/g, ' ').trim()
  return title && title !== body ? title : ''
}

/** Nội dung thân nút đã bỏ đầu số hiệu nếu OCR gộp vào. */
export function bodyOf(node: ClauseNode) {
  const body = node.text.replace(/\s+/g, ' ').trim()
  const head = headOf(node)
  if (head && body.toLowerCase().startsWith(head.toLowerCase())) {
    return body
      .slice(head.length)
      .replace(/^[\s.:\-–—)]+/, '')
      .trim()
  }
  return body
}

/** Nhãn ngắn hiện trên hộp / dòng: số hiệu + tiêu đề (hoặc trích đoạn). */
export function nodeLabel(node: ClauseNode) {
  const head = headOf(node)
  const title = titleOf(node)
  const body = node.text.replace(/\s+/g, ' ').trim()
  const detail = title || body
  if (head && detail && !detail.toLowerCase().startsWith(head.toLowerCase())) {
    return `${head}. ${shortText(detail, 140)}`
  }
  if (detail) return shortText(detail, 160)
  return head || kindOf(node)
}

/** Nhãn đầy đủ dùng cho tooltip và file dữ liệu. */
export function fullLabel(node: ClauseNode) {
  const head = headOf(node)
  const title = cleanToken(node.title ?? '')
  const body = node.text.replace(/\s+/g, ' ').trim()
  if (head && body && !body.toLowerCase().startsWith(head.toLowerCase())) {
    return `${head}: ${body}`
  }
  if (body) return body
  if (title) return title
  return head || kindOf(node)
}

export function countOf(nodes: ClauseNode[], type: string): number {
  return nodes.reduce(
    (total, node) =>
      total + (node.nodeType === type ? 1 : 0) + countOf(node.children, type),
    0,
  )
}

export function hasVisibleContent(node: ClauseNode): boolean {
  if (node.children.some(hasVisibleContent)) return true
  return Boolean(
    node.text.trim() ||
    node.label.trim() ||
    node.title?.trim() ||
    node.number?.trim(),
  )
}

export function visibleChildren(node: ClauseNode) {
  return node.children.filter(hasVisibleContent)
}

export function visibleRoots(nodes: ClauseNode[]) {
  return nodes.filter(hasVisibleContent)
}

export function dataDepth(nodes: ClauseNode[], depth = 1): number {
  let max = 0
  for (const node of visibleRoots(nodes)) {
    max = Math.max(max, depth)
    const kids = visibleChildren(node)
    if (kids.length > 0) max = Math.max(max, dataDepth(kids, depth + 1))
  }
  return max
}

/** id nút → id cha (null với nút gốc). */
export function parentMap(nodes: ClauseNode[]) {
  const parents = new Map<string, string | null>()
  function walk(list: ClauseNode[], parent: string | null) {
    for (const node of list) {
      parents.set(node.id, parent)
      walk(node.children, node.id)
    }
  }
  walk(nodes, null)
  return parents
}

/** id → chỉ số nhánh cấp 1 chứa nút, để tô màu nhất quán giữa các kiểu xem. */
export function branchMap(nodes: ClauseNode[]) {
  const branches = new Map<string, number>()
  function walk(list: ClauseNode[], branch: number) {
    for (const node of list) {
      branches.set(node.id, branch)
      walk(node.children, branch)
    }
  }
  visibleRoots(nodes).forEach((node, index) => {
    branches.set(node.id, index)
    walk(node.children, index)
  })
  return branches
}

/** Mọi nút có con hiển thị được. */
export function expandableIds(nodes: ClauseNode[]) {
  const ids = new Set<string>()
  function walk(list: ClauseNode[]) {
    for (const node of list) {
      const kids = visibleChildren(node)
      if (kids.length > 0) {
        ids.add(node.id)
        walk(kids)
      }
    }
  }
  walk(visibleRoots(nodes))
  return ids
}

/** Tập id gồm mọi cấp cha của nút. */
export function ancestorIds(
  id: string,
  parents: ReadonlyMap<string, string | null>,
) {
  const ids = new Set<string>()
  let cursor = parents.get(id) ?? null
  while (cursor) {
    ids.add(cursor)
    cursor = parents.get(cursor) ?? null
  }
  return ids
}

/** Khoảng trang "tr. 3" hoặc "tr. 3–5", rỗng nếu không có số trang hợp lệ. */
export function pageRange(node: ClauseNode) {
  const start = node.pageStart > 0 ? node.pageStart : 0
  const end = node.pageEnd > 0 ? node.pageEnd : start
  if (!start) return ''
  return end > start ? `tr. ${start}–${end}` : `tr. ${start}`
}

export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

/** File .txt thụt dòng theo cấp, dùng chung cho nút "Xuất dữ liệu". */
export function exportOutlineText(title: string, nodes: ClauseNode[]) {
  const lines: string[] = [title]
  function walk(list: ClauseNode[], depth: number) {
    for (const node of list) {
      lines.push(`${'  '.repeat(depth)}${fullLabel(node)}`)
      walk(node.children, depth + 1)
    }
  }
  walk(nodes, 0)
  downloadBlob(
    'du-lieu-hop-dong.txt',
    new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }),
  )
}
