import { useMemo, useState } from 'react'
import type { ClauseNode } from '../api/structure'
import { MaterialIcon } from './icons'

const typeLabels: Record<string, string> = {
  article: 'Điều',
  clause: 'Khoản',
  point: 'Điểm',
  unmarked: 'Đoạn',
  annex: 'Phụ lục',
  preamble: 'Mở đầu',
  signature_block: 'Chữ ký',
}

function nodeTitle(node: ClauseNode) {
  const title = node.title?.trim() || node.label.trim()
  const number = node.number?.trim()
  if (number && title && title !== number) return `${number} · ${title}`
  return title || number || 'Mục chưa đặt tên'
}

function pageLabel(node: ClauseNode) {
  if (!node.pageStart) return null
  if (!node.pageEnd || node.pageEnd === node.pageStart) {
    return `Trang ${node.pageStart}`
  }
  return `Trang ${node.pageStart}–${node.pageEnd}`
}

function nodeMatches(node: ClauseNode, needle: string) {
  if (!needle) return true
  const haystack = [node.number, node.title, node.label, node.text]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return haystack.includes(needle)
}

export function filterClauses(nodes: ClauseNode[], needle: string): ClauseNode[] {
  if (!needle) return nodes
  return nodes.flatMap((node) => {
    const children = filterClauses(node.children, needle)
    if (nodeMatches(node, needle)) return [{ ...node, children: node.children }]
    if (children.length === 0) return []
    return [{ ...node, children }]
  })
}

function needsAttention(node: ClauseNode, attentionIds?: ReadonlySet<string>) {
  return (
    attentionIds?.has(node.id) === true ||
    (node.confidence !== null && node.confidence < 0.6)
  )
}

function branchNeedsAttention(
  node: ClauseNode,
  attentionIds?: ReadonlySet<string>,
): boolean {
  if (needsAttention(node, attentionIds)) return true
  return node.children.some((child) =>
    branchNeedsAttention(child, attentionIds),
  )
}

function ClauseBranch({
  node,
  depth,
  attentionIds,
  forceOpen,
}: {
  node: ClauseNode
  depth: number
  attentionIds?: ReadonlySet<string>
  forceOpen: boolean
}) {
  const flagged = needsAttention(node, attentionIds)
  const [open, setOpen] = useState(
    depth < 2 || branchNeedsAttention(node, attentionIds),
  )
  const hasChildren = node.children.length > 0
  const expanded = forceOpen || open
  const pages = pageLabel(node)
  const excerpt = node.text.trim()

  return (
    <li className="flex flex-col">
      <div
        className="flex items-start gap-space-sm py-space-sm"
        style={{ paddingLeft: `${depth * 1.25}rem` }}
      >
        {hasChildren ? (
          <button
            className="mt-0.5 w-6 h-6 rounded hover:bg-surface-container flex items-center justify-center text-on-surface-variant shrink-0"
            type="button"
            aria-expanded={expanded}
            onClick={() => setOpen((current) => !current)}
          >
            <MaterialIcon
              name={expanded ? 'expand_more' : 'chevron_right'}
              className="text-[18px]"
            />
          </button>
        ) : (
          <span className="mt-1.5 w-6 flex justify-center shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-outline-variant" />
          </span>
        )}
        <div className="min-w-0 flex flex-col gap-1">
          <div className="flex items-center gap-space-sm flex-wrap">
            <span className="font-label-sm text-[11px] uppercase tracking-wider px-2 py-0.5 rounded bg-surface-container text-secondary">
              {typeLabels[node.nodeType] ?? node.nodeType}
            </span>
            <span className="font-title-sm text-title-sm text-on-surface">
              {nodeTitle(node)}
            </span>
            {flagged ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-error-container text-on-error-container font-label-sm text-[11px] font-semibold">
                <MaterialIcon name="warning" className="text-[13px]" />
                Cần xử lý
              </span>
            ) : null}
            {pages ? (
              <span className="font-code-sm text-code-sm text-on-surface-variant">
                {pages}
              </span>
            ) : null}
          </div>
          {excerpt ? (
            <p className="font-body-sm text-body-sm text-on-surface-variant line-clamp-3 whitespace-pre-wrap">
              {excerpt}
            </p>
          ) : null}
        </div>
      </div>
      {hasChildren && expanded ? (
        <ul className="flex flex-col border-l border-outline-variant/40 ml-3">
          {node.children.map((child) => (
            <ClauseBranch
              key={child.id}
              node={child}
              depth={depth + 1}
              attentionIds={attentionIds}
              forceOpen={forceOpen}
            />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

export function ClauseTree({
  nodes,
  query = '',
  attentionIds,
}: {
  nodes: ClauseNode[]
  query?: string
  attentionIds?: ReadonlySet<string>
}) {
  const needle = query.trim().toLowerCase()
  const visible = useMemo(() => filterClauses(nodes, needle), [needle, nodes])

  if (nodes.length === 0) {
    return (
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        OCR đã xong, nhưng tài liệu chưa có nút cấu trúc.
      </p>
    )
  }

  if (visible.length === 0) {
    return (
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        Không có điều khoản khớp “{query.trim()}”.
      </p>
    )
  }

  return (
    <ul className="flex flex-col divide-y divide-surface-container">
      {visible.map((node) => (
        <ClauseBranch
          key={node.id}
          node={node}
          depth={0}
          attentionIds={attentionIds}
          forceOpen={needle.length > 0}
        />
      ))}
    </ul>
  )
}
