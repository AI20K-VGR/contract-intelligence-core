import { useEffect, useMemo, useRef, useState } from 'react'
import type { ClauseNode } from '../api/structure'
import {
  bodyOf,
  branchMap,
  countOf,
  exportOutlineText,
  fullLabel,
  headOf,
  kindOf,
  pageRange,
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
  HeaderDivider,
  IconButton,
  ViewShell,
} from './StructureViewShell'

/*
 * Văn bản: mục lục dính bên trái, toàn văn hợp đồng chạy theo đúng cây bên phải.
 * Cuộn tới đâu mục lục sáng tới đó; bấm mục lục để nhảy tới điều / khoản.
 */

const TOC_DEPTH = 2

type TocItem = { node: ClauseNode; depth: number; branch: number }

function tocItems(
  nodes: ClauseNode[],
  branches: ReadonlyMap<string, number>,
): TocItem[] {
  const items: TocItem[] = []
  function walk(node: ClauseNode, depth: number) {
    items.push({ node, depth, branch: branches.get(node.id) ?? 0 })
    if (depth < TOC_DEPTH)
      for (const kid of visibleChildren(node)) walk(kid, depth + 1)
  }
  for (const node of visibleRoots(nodes)) walk(node, 1)
  return items
}

function pageSpan(nodes: ClauseNode[]) {
  let min = Number.POSITIVE_INFINITY
  let max = 0
  function walk(node: ClauseNode) {
    if (node.pageStart > 0) min = Math.min(min, node.pageStart)
    if (node.pageEnd > 0) max = Math.max(max, node.pageEnd)
    node.children.forEach(walk)
  }
  nodes.forEach(walk)
  return Number.isFinite(min) && max >= min ? max - min + 1 : 0
}

export function StructureDocument({
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
  const branches = useMemo(() => branchMap(source), [source])
  const toc = useMemo(() => tocItems(source, branches), [source, branches])
  const [tocOpen, setTocOpen] = useState(true)
  const [current, setCurrent] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const paneRef = useRef<HTMLDivElement | null>(null)
  const tocRef = useRef<HTMLElement | null>(null)

  const articleCount = countOf(nodes, 'article') || visibleRoots(nodes).length
  const pages = pageSpan(nodes)
  const caption = `${articleCount} điều khoản${pages ? ` • ${pages} trang` : ''}`

  // Scroll-spy: mục đang đọc là mục lục cuối cùng có đỉnh nằm trên vạch 1/4 khung.
  useEffect(() => {
    const pane = paneRef.current
    if (!pane) return
    let frame = 0
    function measure() {
      frame = 0
      if (!pane) return
      const line = pane.getBoundingClientRect().top + pane.clientHeight * 0.25
      let hit: string | null = null
      for (const item of toc) {
        const el = pane.querySelector<HTMLElement>(
          `[data-section-id="${CSS.escape(item.node.id)}"]`,
        )
        if (!el) continue
        if (el.getBoundingClientRect().top <= line) hit = item.node.id
        else break
      }
      setCurrent(hit ?? toc[0]?.node.id ?? null)
    }
    function onScroll() {
      if (!frame) frame = window.requestAnimationFrame(measure)
    }
    measure()
    pane.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      pane.removeEventListener('scroll', onScroll)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [toc])

  // Giữ mục đang đọc trong tầm nhìn của mục lục.
  useEffect(() => {
    if (!current) return
    const el = tocRef.current?.querySelector<HTMLElement>(
      `[data-toc-id="${CSS.escape(current)}"]`,
    )
    el?.scrollIntoView({ block: 'nearest' })
  }, [current])

  useEffect(() => {
    if (!focusId) return
    const frame = window.requestAnimationFrame(() => {
      paneRef.current
        ?.querySelector(`[data-section-id="${CSS.escape(focusId)}"]`)
        ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [focusId])

  function jumpTo(id: string) {
    paneRef.current
      ?.querySelector(`[data-section-id="${CSS.escape(id)}"]`)
      ?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    setCurrent(id)
  }

  function pick(id: string) {
    setSelected(id)
    onCite?.(id)
  }

  if (nodes.length === 0) return <EmptyStructure />

  return (
    <ViewShell
      caption={caption}
      controls={
        <>
          <IconButton
            active={tocOpen}
            icon="toc"
            label={tocOpen ? 'Ẩn mục lục' : 'Hiện mục lục'}
            onClick={() => setTocOpen((open) => !open)}
          />
          <HeaderDivider />
          <IconButton
            icon="download"
            label="Xuất dữ liệu (TXT)"
            onClick={() => exportOutlineText(title, nodes)}
          />
        </>
      }
      icon="article"
      title="Văn bản"
    >
      <div className="flex min-h-0 flex-1">
        {tocOpen ? (
          <nav
            ref={tocRef}
            aria-label="Mục lục"
            className="hidden w-72 shrink-0 overflow-auto border-r border-outline-variant/20 bg-surface-container-low/40 py-3 md:block"
          >
            <p className="px-4 pb-2 font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
              Mục lục
            </p>
            <ol>
              {toc.map((item) => {
                const tone = toneAt(item.branch)
                const active = current === item.node.id
                const head = headOf(item.node)
                const label = titleOf(item.node) || bodyOf(item.node)
                return (
                  <li key={item.node.id}>
                    <button
                      aria-current={active ? 'true' : undefined}
                      className={`relative flex w-full items-start gap-2 py-1.5 pr-3 text-left text-[12.5px] leading-5 transition-colors ${
                        active
                          ? 'bg-white font-semibold text-on-surface'
                          : 'text-on-surface-variant hover:bg-white/70 hover:text-on-surface'
                      }`}
                      data-toc-id={item.node.id}
                      style={{ paddingLeft: 12 + (item.depth - 1) * 16 }}
                      type="button"
                      onClick={() => jumpTo(item.node.id)}
                    >
                      {active ? (
                        <span
                          className="absolute inset-y-0 left-0 w-[3px]"
                          style={{ backgroundColor: tone.line }}
                        />
                      ) : null}
                      {head ? (
                        <span
                          className="shrink-0 font-semibold"
                          style={{ color: tone.line }}
                        >
                          {head}
                        </span>
                      ) : null}
                      <span className="line-clamp-2 min-w-0">
                        {label || kindOf(item.node)}
                      </span>
                      {attentionIds?.has(item.node.id) ? (
                        <AttentionStar size={13} />
                      ) : null}
                    </button>
                  </li>
                )
              })}
            </ol>
          </nav>
        ) : null}
        <div ref={paneRef} className="min-h-0 flex-1 overflow-auto bg-white">
          <article className="mx-auto max-w-3xl px-8 py-8 pb-24">
            <h1 className="mb-6 border-b border-outline-variant/30 pb-4 font-headline-md text-headline-md text-primary">
              {title}
            </h1>
            {visibleRoots(source).map((node) => (
              <Section
                key={node.id}
                attentionIds={attentionIds}
                branch={branches.get(node.id) ?? 0}
                citationOf={citationOf}
                depth={1}
                focusId={focusId}
                node={node}
                selected={selected}
                onPick={pick}
              />
            ))}
          </article>
        </div>
      </div>
    </ViewShell>
  )
}

function Section({
  node,
  depth,
  branch,
  attentionIds,
  citationOf,
  focusId,
  selected,
  onPick,
}: {
  node: ClauseNode
  depth: number
  branch: number
  attentionIds?: ReadonlySet<string>
  citationOf?: ReadonlyMap<string, number>
  focusId?: string | null
  selected: string | null
  onPick: (id: string) => void
}) {
  const tone = toneAt(branch)
  const head = headOf(node)
  const rawBody = bodyOf(node)
  // Điều không có tiêu đề riêng nhưng thân ngắn thì dùng thân làm tiêu đề.
  const heading =
    titleOf(node) || (depth === 1 && rawBody.length <= 100 ? rawBody : '')
  const body = rawBody === heading ? '' : rawBody
  const flagged = attentionIds?.has(node.id) === true
  const active = selected === node.id || focusId === node.id
  const pages = pageRange(node)
  const cite = citationOf?.get(node.id)
  const kids = visibleChildren(node)

  const headingClass =
    depth === 1
      ? 'font-title-md text-[17px] font-semibold'
      : depth === 2
        ? 'text-[14.5px] font-semibold'
        : 'text-[13.5px] font-medium'

  return (
    <section
      className={`relative scroll-mt-4 rounded-lg transition-colors ${
        depth === 1 ? 'mt-8 first:mt-0' : 'mt-3'
      } ${active ? 'bg-primary/5 ring-1 ring-primary/20' : ''}`}
      data-section-id={node.id}
      style={{ paddingLeft: depth === 1 ? 0 : 18 }}
    >
      {depth > 1 ? (
        <span
          className="absolute inset-y-1 left-0 w-px"
          style={{ backgroundColor: tone.border }}
        />
      ) : null}
      <div className="group flex items-start gap-2 px-2 py-1">
        <button
          className={`flex min-w-0 flex-1 flex-wrap items-baseline gap-x-2 text-left leading-6 text-on-surface ${headingClass}`}
          title={fullLabel(node)}
          type="button"
          onClick={() => onPick(node.id)}
        >
          {head ? (
            <span
              className={`shrink-0 rounded px-1.5 ${
                depth === 1 ? 'py-0.5' : ''
              }`}
              style={{
                backgroundColor: depth === 1 ? tone.bg : tone.bgSoft,
                color: tone.text,
              }}
            >
              {head}
            </span>
          ) : null}
          {heading ? (
            <span className="min-w-0">{heading}</span>
          ) : !body ? (
            <span className="min-w-0 text-on-surface-variant">
              {kindOf(node)}
            </span>
          ) : null}
        </button>
        <span className="mt-1 flex shrink-0 items-center gap-1.5">
          {flagged ? <AttentionStar /> : null}
          {pages ? (
            <span className="font-mono text-[10px] text-slate-400">
              {pages}
            </span>
          ) : null}
          <CiteBadge
            active={active}
            n={cite}
            tone={tone}
            onClick={() => onPick(node.id)}
          />
          <MaterialIcon
            name="open_in_new"
            className="text-[14px] text-slate-300 opacity-0 transition-opacity group-hover:opacity-100"
          />
        </span>
      </div>
      {body ? (
        <p
          className={`px-2 pb-1 text-[13.5px] leading-6 text-on-surface ${
            heading || depth === 1 ? '' : 'pt-0'
          }`}
        >
          {body}
        </p>
      ) : null}
      {kids.map((kid) => (
        <Section
          key={kid.id}
          attentionIds={attentionIds}
          branch={branch}
          citationOf={citationOf}
          depth={depth + 1}
          focusId={focusId}
          node={kid}
          selected={selected}
          onPick={onPick}
        />
      ))}
    </section>
  )
}
