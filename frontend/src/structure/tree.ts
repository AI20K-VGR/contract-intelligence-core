import type { ClauseNode, ClauseRegion, OpenNode } from './types'

/** Cây hiển thị ít nhất một cấp và không sâu hơn mười cấp. */
export const MIN_TREE_LEVELS = 1
export const MAX_TREE_LEVELS = 10

type Draft = {
  node: ClauseNode
  level: number
  parts: string[]
}

/**
 * Dựng cây từ luồng nút mở theo thứ tự đọc bằng một ngăn xếp.
 *
 * - open(): nút mới level L nằm dưới nút đang mở gần nhất có level < L.
 *   Nút cùng cấp hoặc sâu hơn đang mở bị đóng.
 * - append(): dòng không có ký hiệu nối vào nút đang mở sâu nhất. Nếu chưa
 *   có nút nào mở (phần mở đầu, thông tin các bên) thì bỏ, không tạo nút.
 */
export class TreeBuilder {
  private roots: Draft[] = []
  private stack: Draft[] = []
  private created: Draft[] = []

  get depth() {
    return this.stack.length
  }

  open(input: OpenNode) {
    while (
      this.stack.length > 0 &&
      this.stack[this.stack.length - 1].level >= input.level
    ) {
      this.stack.pop()
    }
    while (this.stack.length >= MAX_TREE_LEVELS) {
      this.stack.pop()
    }
    const draft: Draft = {
      level: input.level,
      parts: input.text.trim() ? [input.text.trim()] : [],
      node: {
        id: input.id,
        nodeType: input.nodeType,
        label: input.label,
        number: input.number,
        title: input.title,
        text: '',
        pageStart: input.pageNo,
        pageEnd: input.pageNo,
        confidence: null,
        regions: input.regions ?? [],
        children: [],
      },
    }
    const parent = this.stack[this.stack.length - 1]
    if (parent) {
      parent.node.children.push(draft.node)
    } else {
      this.roots.push(draft)
    }
    this.stack.push(draft)
    this.created.push(draft)
  }

  /** Trả về false khi chưa có nút nào mở để nối vào. */
  append(text: string, pageNo: number, region?: ClauseRegion | null) {
    const current = this.stack[this.stack.length - 1]
    if (!current) return false
    const trimmed = text.trim()
    if (trimmed) current.parts.push(trimmed)
    if (region) current.node.regions.push(region)
    for (const draft of this.stack) {
      draft.node.pageEnd = Math.max(draft.node.pageEnd, pageNo)
    }
    return true
  }

  build(): ClauseNode[] {
    for (const draft of this.created) {
      draft.node.text = draft.parts.join(' ').replace(/\s+/g, ' ').trim()
    }
    return capToMaxLevels(this.roots.map((draft) => draft.node))
  }
}

/**
 * Giữ đúng độ sâu OCR trả về, nhưng không quá 10 cấp.
 * Nút sâu hơn được kéo lên cùng cấp 10, không bị bỏ.
 */
export function capToMaxLevels(
  nodes: ClauseNode[],
  depth = MIN_TREE_LEVELS,
): ClauseNode[] {
  return nodes.flatMap((node) => {
    if (depth >= MAX_TREE_LEVELS) {
      return [
        { ...node, children: [] },
        ...capToMaxLevels(node.children, depth),
      ]
    }
    return [
      {
        ...node,
        children: capToMaxLevels(node.children, depth + 1),
      },
    ]
  })
}
