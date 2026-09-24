import { useEffect, useMemo, useRef, useState } from 'react'
import type { ClauseNode } from '../api/structure'
import {
  ancestorIds,
  bodyOf,
  branchMap,
  dataDepth,
  expandableIds,
  exportOutlineText,
  fullLabel,
  headOf,
  kindOf,
  pageRange,
  parentMap,
  titleOf,
  toneAt,
  visibleChildren,
  visibleRoots,
} from '../structure/display'
import { capToMaxLevels } from '../structure/tree'
import { MaterialIcon } from './icons'
import {
  AttentionStar,
  CiteBadge,
  EmptyStructure,
  FilterField,
  HeaderDivider,
  Highlight,
  IconButton,
  ViewShell,
} from './StructureViewShell'

/*
 * Dàn bài: cây dọc thụt đầu dòng kiểu trình quản lý file.
 * Mở / thu từng nút, mở rộng / thu gọn tất cả, lọc nhanh theo chữ
 * (khi lọc, chỉ hiện nút khớp và các cấp cha, tự mở hết).
 */

type Row = {
  node: ClauseNode
  depth: number
  branch: number
  expandable: boolean
  open: boolean
}

function matches(node: ClauseNode, needle: string) {
  if (!needle) return true
  return fullLabel(node).toLowerCase().includes(needle)
}

/** Với bộ lọc: id các nút khớp hoặc chứa nút khớp. */
function matchSet(nodes: ClauseNode[], needle: string) {
  const keep = new Set<string>()
  function walk(node: ClauseNode): boolean {
    let hit = matches(node, needle)
    for (const kid of visibleChildren(node)) {
      if (walk(kid)) hit = true
    }
    if (hit) keep.add(node.id)
    return hit
  }
  for (const node of visibleRoots(nodes)) walk(node)
  return keep
}

function flatten(
  nodes: ClauseNode[],
  expanded: ReadonlySet<string>,
  branches: ReadonlyMap<string, number>,
  keep: ReadonlySet<string> | null,
): Row[] {
  const rows: Row[] = []
  function walk(node: ClauseNode, depth: number) {
    if (keep && !keep.has(node.id)) return
    const kids = visibleChildren(node).filter(
      (kid) => !keep || keep.has(kid.id),
    )
    const expandable = kids.length > 0
    const open = expandable && (keep ? true : expanded.has(node.id))
    rows.push({
      node,
      depth,
      branch: branches.get(node.id) ?? 0,
      expandable,
      open,
    })
    if (open) for (const kid of kids) walk(kid, depth + 1)
  }
  for (const node of visibleRoots(nodes)) walk(node, 1)
  return rows
}

function countAll(nodes: ClauseNode[]): number {
  return visibleRoots(nodes).reduce(
    (sum, node) => sum + 1 + countAll(node.children),
    0,
  )
}

export function StructureOutline({
  title,
  nodes,
  attentionIds,
  citationOf,
  focusId,
  onCite,
}: {
  title: string
  nodes: ClauseNode[]
  attentionIds?: ReadonlySet<string>
  citationOf?: ReadonlyMap<string, number>
  focusId?: string | null
  onCite?: (id: string) => void
}) {
  const source = useMemo(() => capToMaxLevels(nodes), [nodes])
  const parents = useMemo(() => parentMap(source), [source])
  const branches = useMemo(() => branchMap(source), [source])
  const total = useMemo(() => countAll(source), [source])
  const depth = useMemo(() => dataDepth(source), [source])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  // Mặc định mở cấp 1 để thấy ngay các khoản.
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(
    () => new Set(visibleRoots(source).map((node) => node.id)),
  )
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    setExpanded(new Set(visibleRoots(source).map((node) => node.id)))
    setSelected(null)
    setQuery('')
  }, [source])

  const needle = query.trim().toLowerCase()
  const keep = useMemo(
    () => (needle ? matchSet(source, needle) : null),
    [source, needle],
  )
  const rows = useMemo(
    () => flatten(source, expanded, branches, keep),
    [source, expanded, branches, keep],
  )

  useEffect(() => {
    if (!focusId) return
    setExpanded((current) => {
      const next = new Set(current)
      for (const id of ancestorIds(focusId, parents)) next.add(id)
      return next.size === current.size ? current : next
    })
    const frame = window.requestAnimationFrame(() => {
      listRef.current
        ?.querySelector(`[data-node-id="${CSS.escape(focusId)}"]`)
        ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [focusId, parents])

  function toggle(id: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function pick(id: string) {
    setSelected(id)
    onCite?.(id)
  }

  if (nodes.length === 0) return <EmptyStructure />

  const caption = keep
    ? `${keep.size}/${total} nút khớp • ${depth} cấp`
    : `${rows.length}/${total} nút đang hiện • ${depth} cấp`

  return (
    <ViewShell
      caption={caption}
      controls={
        <>
          <FilterField
            placeholder="Lọc điều, khoản, nội dung…"
            value={query}
            onChange={setQuery}
          />
          <IconButton
            icon="unfold_more"
            label="Mở rộng tất cả"
            onClick={() => setExpanded(expandableIds(source))}
          />
          <IconButton
            icon="unfold_less"
            label="Thu gọn tất cả"
            onClick={() => setExpanded(new Set())}
          />
          <HeaderDivider />
          <IconButton
            icon="download"
            label="Xuất dữ liệu (TXT)"
            onClick={() => exportOutlineText(title, nodes)}
          />
        </>
      }
      icon="format_list_bulleted"
      title="Dàn bài"
    >
      <div
        ref={listRef}
        className="min-h-0 flex-1 overflow-auto bg-[#fafbff] py-2"
        role="tree"
      >
        {rows.length === 0 ? (
          <p className="px-6 py-8 text-center font-body-sm text-body-sm text-on-surface-variant">
            Không có nút nào khớp "{query.trim()}".
          </p>
        ) : null}
        {rows.map((row) => (
          <OutlineRow
            key={row.node.id}
            active={selected === row.node.id || focusId === row.node.id}
            cite={citationOf?.get(row.node.id)}
            flagged={attentionIds?.has(row.node.id) === true}
            query={needle}
            row={row}
            onPick={() => pick(row.node.id)}
            onToggle={() => toggle(row.node.id)}
          />
        ))}
      </div>
    </ViewShell>
  )
}

function OutlineRow({
  row,
  active,
  flagged,
  cite,
  query,
  onPick,
  onToggle,
}: {
  row: Row
  active: boolean
  flagged: boolean
  cite: number | undefined
  query: string
  onPick: () => void
  onToggle: () => void
}) {
  const { node, depth } = row
  const tone = toneAt(row.branch)
  const head = headOf(node)
  const heading = titleOf(node)
  const rawBody = bodyOf(node)
  const body = rawBody === heading ? '' : rawBody
  const primary = heading || (depth === 1 ? body : '')
  const excerpt = heading ? body : depth === 1 ? '' : body
  const pages = pageRange(node)

  return (
    <div
      aria-expanded={row.expandable ? row.open : undefined}
      aria-level={depth}
      className={`group relative flex items-start gap-1 pr-4 transition-colors ${
        active ? 'bg-primary/5' : 'hover:bg-slate-100/70'
      }`}
      data-node-id={node.id}
      role="treeitem"
      style={{ paddingLeft: 8 + (depth - 1) * 22 }}
    >
      {active ? (
        <span
          className="absolute inset-y-0 left-0 w-[3px]"
          style={{ backgroundColor: tone.line }}
        />
      ) : null}
      {Array.from({ length: depth - 1 }, (_, index) => (
        <span
          key={index}
          className="pointer-events-none absolute inset-y-0 w-px bg-slate-200"
          style={{ left: 8 + index * 22 + 10 }}
        />
      ))}
      <button
        aria-label={
          row.expandable ? (row.open ? 'Thu nhánh' : 'Mở nhánh') : undefined
        }
        className={`mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
          row.expandable
            ? 'text-slate-500 hover:bg-slate-200/80 hover:text-slate-900'
            : 'cursor-default'
        }`}
        disabled={!row.expandable}
        tabIndex={row.expandable ? 0 : -1}
        type="button"
        onClick={onToggle}
      >
        {row.expandable ? (
          <MaterialIcon
            name="chevron_right"
            className={`text-[18px] transition-transform ${
              row.open ? 'rotate-90' : ''
            }`}
          />
        ) : (
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: tone.line }}
          />
        )}
      </button>
      <button
        className="flex min-w-0 flex-1 items-start gap-2 py-1.5 text-left"
        title={fullLabel(node)}
        type="button"
        onClick={onPick}
      >
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-baseline gap-x-2">
            {head ? (
              <span
                className={`shrink-0 rounded px-1.5 py-px text-[11px] font-semibold ${
                  depth === 1 ? '' : 'bg-transparent'
                }`}
                style={{
                  backgroundColor: depth === 1 ? tone.bg : tone.bgSoft,
                  color: tone.text,
                }}
              >
                <Highlight text={head} query={query} />
              </span>
            ) : (
              <span
                className="shrink-0 rounded px-1.5 py-px text-[11px] font-medium text-slate-600"
                style={{ backgroundColor: tone.bgSoft }}
              >
                {kindOf(node)}
              </span>
            )}
            {primary ? (
              <span
                className={`min-w-0 text-[13px] leading-5 ${
                  depth === 1
                    ? 'font-semibold text-on-surface'
                    : 'font-medium text-on-surface'
                }`}
              >
                <Highlight text={primary} query={query} />
              </span>
            ) : null}
          </span>
          {excerpt ? (
            <span className="mt-0.5 block truncate text-[12px] leading-5 text-on-surface-variant group-hover:whitespace-normal">
              <Highlight text={excerpt} query={query} />
            </span>
          ) : null}
        </span>
        <span className="mt-0.5 flex shrink-0 items-center gap-1.5">
          {flagged ? <AttentionStar /> : null}
          {pages ? (
            <span className="font-mono text-[10px] text-slate-400">
              {pages}
            </span>
          ) : null}
          <CiteBadge active={active} n={cite} tone={tone} />
        </span>
      </button>
    </div>
  )
}
