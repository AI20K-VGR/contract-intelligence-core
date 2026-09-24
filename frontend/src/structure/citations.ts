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
