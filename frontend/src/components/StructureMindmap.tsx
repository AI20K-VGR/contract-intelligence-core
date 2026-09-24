import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'
import type { ClauseNode } from '../api/structure'
import { citationNumbers } from '../structure/citations'
import { MaterialIcon } from './icons'

const typeLabels: Record<string, string> = {
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

const palette = [
  {
    color: '#1e3a8a',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-950',
    link: 'border-blue-800',
    hover: 'hover:text-blue-900',
    tone: 'sky' as const,
  },
  {
    color: '#0284c7',
    bg: 'bg-sky-50',
    border: 'border-sky-200',
    text: 'text-sky-950',
    link: 'border-sky-600',
    hover: 'hover:text-sky-800',
    tone: 'sky' as const,
  },
  {
    color: '#059669',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    text: 'text-emerald-950',
    link: 'border-emerald-600',
    hover: 'hover:text-emerald-800',
    tone: 'emerald' as const,
  },
  {
    color: '#d97706',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-950',
    link: 'border-amber-500',
    hover: 'hover:text-amber-800',
    tone: 'emerald' as const,
  },
  {
    color: '#e11d48',
    bg: 'bg-rose-50',
    border: 'border-rose-200',
    text: 'text-rose-950',
    link: 'border-rose-600',
    hover: 'hover:text-rose-800',
    tone: 'rose' as const,
  },
]

const annexTones = {
  sky: 'text-sky-800 bg-sky-100/80 border-sky-200',
  emerald: 'text-emerald-800 bg-emerald-100/80 border-emerald-200',
  rose: 'text-rose-800 bg-rose-100/80 border-rose-200',
}

function cleanToken(value: string) {
  return value
    .replace(/^(article|clause|point|unmarked|section|annex)[_\s-]*/i, '')
    .replace(/unnumbered[_\s-]*/i, '')
    .replace(/_/g, ' ')
    .trim()
}

function shortText(text: string, max = 68) {
  const line = text.replace(/\s+/g, ' ').trim()
  if (!line) return ''
  if (line.length <= max) return line
  return `${line.slice(0, max - 1)}…`
}

function chipLabel(node: ClauseNode) {
  const kind = typeLabels[node.nodeType] ?? 'Mục'
  const number = cleanToken(node.number ?? '')
  if (number) {
    return number.toLowerCase().startsWith(kind.toLowerCase())
      ? number
      : `${kind} ${number}`
  }
  return shortText(node.title ?? '', 36) || shortText(node.text, 36) || kind
}

function linkLabel(node: ClauseNode) {
  const kind = typeLabels[node.nodeType] ?? 'Mục'
  const number = cleanToken(node.number ?? '')
  const title = cleanToken(node.title ?? '')
  const excerpt = shortText(node.text)
  const head = number || (title && title !== excerpt ? title : '')
  if (head && excerpt && !excerpt.startsWith(head)) {
    const prefix = head.toLowerCase().startsWith(kind.toLowerCase())
      ? head
      : `${kind} ${head}`
    return `${prefix}: ${excerpt}`
  }
  if (excerpt) return excerpt
  return chipLabel(node)
}

function fullLabel(node: ClauseNode) {
  const kind = typeLabels[node.nodeType] ?? 'Mục'
  const number = cleanToken(node.number ?? '')
  const title = cleanToken(node.title ?? '')
  const body = node.text.replace(/\s+/g, ' ').trim()
  const head = number || (title && title !== body ? title : '')
  if (head && body && !body.toLowerCase().startsWith(head.toLowerCase())) {
    const prefix = head.toLowerCase().startsWith(kind.toLowerCase())
      ? head
      : `${kind} ${head}`
    return `${prefix}: ${body}`
  }
  if (body) return body
  if (title) return title
  if (number) {
    return number.toLowerCase().startsWith(kind.toLowerCase())
      ? number
      : `${kind} ${number}`
  }
  return kind
}

function countOf(nodes: ClauseNode[], type: string): number {
  return nodes.reduce(
    (total, node) =>
      total + (node.nodeType === type ? 1 : 0) + countOf(node.children, type),
    0,
  )
}

type Placed = { node: ClauseNode; y: number }

function layoutBranches(nodes: ClauseNode[]) {
  const branches: { node: ClauseNode; y: number; children: Placed[] }[] = []
  let cursor = 56
  for (const node of nodes) {
    const kids = node.children
    if (kids.length === 0) {
      branches.push({ node, y: cursor, children: [] })
      cursor += 72
      continue
    }
    const children = kids.map((child) => {
      const placed = { node: child, y: cursor }
      cursor += 40
      return placed
    })
    const y = (children[0].y + children[children.length - 1].y) / 2
    branches.push({ node, y, children })
    cursor += 22
  }
  return { branches, height: Math.max(620, cursor + 48) }
}

function curve(x1: number, y1: number, x2: number, y2: number) {
  const mid = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`
}

const chipPaint = [
  {
    color: '#1e3a8a',
    bg: '#eff6ff',
    border: '#bfdbfe',
    text: '#172554',
    link: '#1e3a8a',
    annexBg: '#e0f2fe',
    annexBorder: '#bae6fd',
    annexText: '#075985',
  },
  {
    color: '#0284c7',
    bg: '#f0f9ff',
    border: '#bae6fd',
    text: '#082f49',
    link: '#0284c7',
    annexBg: '#e0f2fe',
    annexBorder: '#bae6fd',
    annexText: '#075985',
  },
  {
    color: '#059669',
    bg: '#ecfdf5',
    border: '#a7f3d0',
    text: '#022c22',
    link: '#059669',
    annexBg: '#d1fae5',
    annexBorder: '#a7f3d0',
    annexText: '#065f46',
  },
  {
    color: '#d97706',
    bg: '#fffbeb',
    border: '#fde68a',
    text: '#451a03',
    link: '#d97706',
    annexBg: '#d1fae5',
    annexBorder: '#a7f3d0',
    annexText: '#065f46',
  },
  {
    color: '#e11d48',
    bg: '#fff1f2',
    border: '#fecdd3',
    text: '#4c0519',
    link: '#e11d48',
    annexBg: '#ffe4e6',
    annexBorder: '#fecdd3',
    annexText: '#9f1239',
  },
]

function fitText(ctx: CanvasRenderingContext2D, text: string, max: number) {
  if (ctx.measureText(text).width <= max) return text
  let next = text
  while (next.length > 1 && ctx.measureText(`${next}…`).width > max) {
    next = next.slice(0, -1)
  }
  return `${next}…`
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  const radius = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.arcTo(x + w, y, x + w, y + h, radius)
  ctx.arcTo(x + w, y + h, x, y + h, radius)
  ctx.arcTo(x, y + h, x, y, radius)
  ctx.arcTo(x, y, x + w, y, radius)
  ctx.closePath()
}

function strokeFan(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  color: string,
  width: number,
) {
  const mid = (x1 + x2) / 2
  ctx.beginPath()
  ctx.moveTo(x1, y1)
  ctx.bezierCurveTo(mid, y1, mid, y2, x2, y2)
  ctx.strokeStyle = color
  ctx.lineWidth = width
  ctx.lineCap = 'round'
  ctx.stroke()
}

function jpegPdf(
  jpeg: Uint8Array,
  pageWidth: number,
  pageHeight: number,
  imageWidth: number,
  imageHeight: number,
) {
  const encoder = new TextEncoder()
  const parts: Uint8Array[] = []
  let cursor = 0
  const add = (bytes: Uint8Array) => {
    parts.push(bytes)
    cursor += bytes.length
  }
  const addText = (value: string) => add(encoder.encode(value))
  addText('%PDF-1.4\n')
  const xref = [0, 0, 0, 0, 0, 0]
  const content = `q\n${pageWidth} 0 0 ${pageHeight} 0 0 cm\n/Im0 Do\nQ\n`
  const objects = [
    '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
    '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
    `3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Contents 4 0 R /Resources << /XObject << /Im0 5 0 R >> >> >>\nendobj\n`,
    `4 0 obj\n<< /Length ${encoder.encode(content).length} >>\nstream\n${content}endstream\nendobj\n`,
  ]
  objects.forEach((body, index) => {
    xref[index + 1] = cursor
    addText(body)
  })
  xref[5] = cursor
  addText(
    `5 0 obj\n<< /Type /XObject /Subtype /Image /Width ${imageWidth} /Height ${imageHeight} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`,
  )
  add(jpeg)
  addText('\nendstream\nendobj\n')
  const xrefAt = cursor
  let table = 'xref\n0 6\n0000000000 65535 f \n'
  for (let index = 1; index <= 5; index += 1) {
    table += `${String(xref[index]).padStart(10, '0')} 00000 n \n`
  }
  addText(table)
  addText(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF`)
  const out = new Uint8Array(cursor)
  let offset = 0
  for (const part of parts) {
    out.set(part, offset)
    offset += part.length
  }
  return new Blob([out], { type: 'application/pdf' })
}

async function mindmapPdf({
  title,
  subtitle,
  nodes,
  attentionIds,
  articleCount,
  annexCount,
}: {
  title: string
  subtitle?: string | null
  nodes: ClauseNode[]
  attentionIds?: ReadonlySet<string>
  articleCount: number
  annexCount: number
}) {
  const layout = layoutBranches(nodes)
  const mapWidth = 1120
  const rootY = layout.branches.length
    ? (layout.branches[0].y + layout.branches[layout.branches.length - 1].y) / 2
    : layout.height / 2
  const pageWidth = mapWidth + 64
  const pageHeight = 52 + 32 + layout.height + 32
  const scale = Math.min(2, 16000 / pageWidth, 16000 / pageHeight)
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.floor(pageWidth * scale))
  canvas.height = Math.max(1, Math.floor(pageHeight * scale))
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Trình duyệt không vẽ được sơ đồ.')
  ctx.scale(scale, scale)
  ctx.fillStyle = '#fafbff'
  ctx.fillRect(0, 0, pageWidth, pageHeight)
  ctx.fillStyle = '#f8fafc'
  ctx.fillRect(0, 0, pageWidth, 52)
  ctx.strokeStyle = '#e2e8f0'
  ctx.beginPath()
  ctx.moveTo(0, 52)
  ctx.lineTo(pageWidth, 52)
  ctx.stroke()
  ctx.fillStyle = '#0f172a'
  ctx.font = '600 15px "Segoe UI", sans-serif'
  ctx.fillText('Sơ Đồ Mindmap Cấu Trúc Hợp Đồng & Phụ Lục', 24, 32)
  const caption = `Dạng cây nhánh cong • ${articleCount} điều khoản${annexCount > 0 ? ` • ${annexCount} phụ lục` : ''}`
  ctx.font = '500 11px "Segoe UI", sans-serif'
  const captionWidth = ctx.measureText(caption).width + 20
  roundRect(ctx, pageWidth - 24 - captionWidth, 16, captionWidth, 22, 11)
  ctx.fillStyle = '#eef2f7'
  ctx.fill()
  ctx.fillStyle = '#64748b'
  ctx.fillText(caption, pageWidth - 14 - captionWidth, 31)

  ctx.save()
  ctx.translate(32, 84)
  for (const [index, branch] of layout.branches.entries()) {
    const paint = chipPaint[index % chipPaint.length]
    strokeFan(ctx, 210, rootY, 340, branch.y + 16, paint.color, 2.5)
    if (branch.children.length === 0) {
      strokeFan(ctx, 520, branch.y + 16, 620, branch.y + 10, paint.color, 1.75)
    } else {
      for (const child of branch.children) {
        strokeFan(ctx, 520, branch.y + 16, 620, child.y + 10, paint.color, 1.75)
      }
    }
  }

  ctx.font = '700 14px "Segoe UI", sans-serif'
  const rootTitle = fitText(ctx, title, 200)
  const rootWidth = Math.min(
    250,
    Math.max(140, ctx.measureText(rootTitle).width + 40),
  )
  roundRect(ctx, 20, rootY - 28, rootWidth, subtitle ? 52 : 44, 26)
  ctx.fillStyle = '#0b1f3a'
  ctx.fill()
  ctx.lineWidth = 2
  ctx.strokeStyle = 'rgba(51,65,85,0.35)'
  ctx.stroke()
  ctx.fillStyle = '#ffffff'
  ctx.fillText(rootTitle, 40, rootY - (subtitle ? 6 : 2))
  if (subtitle) {
    ctx.font = '500 10px ui-monospace, monospace'
    ctx.fillStyle = '#cbd5e1'
    ctx.fillText(fitText(ctx, subtitle, rootWidth - 40), 40, rootY + 12)
  }

  const numbers = citationNumbers(nodes)
  const drawBadge = (x: number, y: number, n: number | undefined) => {
    if (!n) return
    const badge = String(n)
    ctx.font = '600 11px "Segoe UI", sans-serif'
    const badgeWidth = Math.max(18, ctx.measureText(badge).width + 10)
    roundRect(ctx, x, y, badgeWidth, 18, 9)
    ctx.fillStyle = '#ffffff'
    ctx.fill()
    ctx.lineWidth = 1
    ctx.strokeStyle = '#94a3b8'
    ctx.stroke()
    ctx.fillStyle = '#0f172a'
    ctx.fillText(badge, x + 5, y + 13)
  }

  for (const [index, branch] of layout.branches.entries()) {
    const paint = chipPaint[index % chipPaint.length]
    ctx.font = '600 13px "Segoe UI", sans-serif'
    const label = fitText(ctx, chipLabel(branch.node), 140)
    const chipWidth = Math.min(190, ctx.measureText(label).width + 36)
    roundRect(ctx, 340, branch.y, chipWidth, 30, 15)
    ctx.fillStyle = paint.bg
    ctx.fill()
    ctx.lineWidth = 1
    ctx.strokeStyle = paint.border
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(354, branch.y + 15, 4, 0, Math.PI * 2)
    ctx.fillStyle = paint.color
    ctx.fill()
    ctx.fillStyle = paint.text
    ctx.fillText(label, 364, branch.y + 20)
    if (attentionIds?.has(branch.node.id)) {
      ctx.fillStyle = '#f59e0b'
      ctx.fillText('★', 364 + ctx.measureText(label).width + 4, branch.y + 20)
    }
    drawBadge(346 + chipWidth, branch.y + 6, numbers.get(branch.node.id))

    const leaves =
      branch.children.length === 0
        ? [{ node: branch.node, y: branch.y }]
        : branch.children
    for (const child of leaves) {
      const flagged = attentionIds?.has(child.node.id) === true
      if (child.node.nodeType === 'annex' && branch.children.length > 0) {
        ctx.font = '500 11px "Segoe UI", sans-serif'
        const annexLabel = fitText(ctx, chipLabel(child.node), 190)
        const annexWidth = Math.min(220, ctx.measureText(annexLabel).width + 16)
        roundRect(ctx, 860, child.y, annexWidth, 18, 4)
        ctx.fillStyle = paint.annexBg
        ctx.fill()
        ctx.strokeStyle = paint.annexBorder
        ctx.stroke()
        ctx.fillStyle = paint.annexText
        ctx.fillText(annexLabel, 868, child.y + 13)
        drawBadge(866 + annexWidth, child.y, numbers.get(child.node.id))
      } else {
        ctx.font = '500 12px "Segoe UI", sans-serif'
        const text = fitText(ctx, linkLabel(child.node), 280)
        ctx.fillStyle = '#334155'
        ctx.fillText(text, 620, child.y + 14)
        const textWidth = ctx.measureText(text).width
        ctx.strokeStyle = paint.link
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(620, child.y + 18)
        ctx.lineTo(620 + textWidth, child.y + 18)
        ctx.stroke()
        if (flagged) {
          ctx.fillStyle = '#f59e0b'
          ctx.fillText('★', 624 + textWidth, child.y + 14)
        }
        if (child.node.id !== branch.node.id) {
          drawBadge(628 + textWidth, child.y - 2, numbers.get(child.node.id))
        }
      }
    }
  }
  ctx.restore()

  const jpeg = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) =>
        blob ? resolve(blob) : reject(new Error('Không tạo được ảnh sơ đồ.')),
      'image/jpeg',
      0.92,
    )
  })
  return jpegPdf(
    new Uint8Array(await jpeg.arrayBuffer()),
    Math.round(pageWidth),
    Math.round(pageHeight),
    canvas.width,
    canvas.height,
  )
}

export function StructureMindmap({
  title,
  subtitle,
  nodes,
  attentionIds,
  citationOf,
  focusId,
  onCite,
}: {
  title: string
  subtitle?: string | null
  nodes: ClauseNode[]
  attentionIds?: ReadonlySet<string>
  citationOf?: ReadonlyMap<string, number>
  focusId?: string | null
  onCite?: (id: string) => void
}) {
  const [zoom, setZoom] = useState(1)
  const [selected, setSelected] = useState<string | null>(null)
  const shellRef = useRef<HTMLDivElement | null>(null)
  const [frame, setFrame] = useState<HTMLElement | null>(null)

  function bindShell(node: HTMLDivElement | null) {
    shellRef.current = node
    const host = node?.closest('[data-structure-frame]')
    const next = host instanceof HTMLElement ? host : null
    setFrame((current) => (current === next ? current : next))
  }
  const layout = useMemo(() => layoutBranches(nodes), [nodes])
  const articleCount = countOf(nodes, 'article') || nodes.length
  const annexCount = countOf(nodes, 'annex')

  useEffect(() => {
    if (!focusId) return
    const target = shellRef.current?.querySelector(
      `[data-node-id="${CSS.escape(focusId)}"]`,
    )
    target?.scrollIntoView({
      block: 'center',
      inline: 'nearest',
      behavior: 'smooth',
    })
  }, [focusId])
  const width = 1120
  const rootY = layout.branches.length
    ? (layout.branches[0].y + layout.branches[layout.branches.length - 1].y) / 2
    : layout.height / 2

  function updateZoom(next: number) {
    setZoom(Math.max(0.1, Math.min(1.4, next)))
  }

  function recenter() {
    updateZoom(1)
    shellRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }

  function toggleFullscreen() {
    const host = shellRef.current?.closest('[data-structure-frame]')
    const node = host instanceof HTMLElement ? host : shellRef.current
    if (!node) return
    if (document.fullscreenElement) {
      void document.exitFullscreen()
    } else {
      void node.requestFullscreen()
    }
  }

  function downloadText(filename: string, lines: string[]) {
    const blob = new Blob([lines.join('\n')], {
      type: 'text/plain;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function exportStructure() {
    const blob = await mindmapPdf({
      title,
      subtitle,
      nodes,
      attentionIds,
      articleCount,
      annexCount,
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'cau-truc-cay.pdf'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  function exportData() {
    const lines: string[] = [title]
    function walk(list: ClauseNode[], depth: number) {
      for (const node of list) {
        lines.push(`${'  '.repeat(depth)}${fullLabel(node)}`)
        walk(node.children, depth + 1)
      }
    }
    walk(nodes, 0)
    downloadText('du-lieu-hop-dong.txt', lines)
  }

  if (nodes.length === 0) {
    return (
      <div className="flex h-full min-h-48 items-center rounded-xl bg-surface-container-lowest px-6 shadow-sm">
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          OCR đã xong, nhưng tài liệu chưa có nút cấu trúc.
        </p>
      </div>
    )
  }

  return (
    <div
      ref={bindShell}
      className="relative flex w-full flex-col overflow-hidden rounded-xl border border-outline-variant/20 bg-surface-container-lowest shadow-sm"
    >
      <div className="px-6 py-3 bg-surface-container-low/60 border-b border-outline-variant/20 flex items-center justify-between z-10 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-2 text-primary font-title-sm text-title-sm min-w-0">
            <MaterialIcon
              name="account_tree"
              className="text-[20px] text-primary shrink-0"
            />
            <span className="font-semibold truncate">
              Sơ Đồ Mindmap Cấu Trúc Hợp Đồng & Phụ Lục
            </span>
          </div>
          <span
            className="hidden xl:inline font-label-sm text-[11px] text-secondary bg-surface-container px-2.5 py-0.5 font-mono shrink-0"
            style={{ borderRadius: '9999px' }}
          >
            Dạng cây nhánh cong • {articleCount} điều khoản
            {annexCount > 0 ? ` • ${annexCount} phụ lục` : ''}
          </span>
        </div>
        <span
          className="flex items-center gap-1.5 text-xs text-secondary bg-surface-container px-2.5 py-1 shrink-0"
          style={{ borderRadius: '9999px' }}
        >
          <span
            className="w-2 h-2 bg-[#059669]"
            style={{ borderRadius: '9999px' }}
          />
          Sơ đồ trực quan tương tác
        </span>
      </div>

      <div className="relative w-full bg-[#fafbff] p-8">
        <div
          className="relative mx-auto"
          style={{ width: width * zoom, height: layout.height * zoom }}
        >
          <div
            className="relative origin-top-left select-none transition-transform duration-200"
            style={{
              width,
              height: layout.height,
              transform: `scale(${zoom})`,
            }}
          >
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none z-0"
              viewBox={`0 0 ${width} ${layout.height}`}
              xmlns="http://www.w3.org/2000/svg"
            >
              {layout.branches.map((branch, index) => {
                const color = palette[index % palette.length].color
                return (
                  <g key={branch.node.id}>
                    <path
                      d={curve(210, rootY, 340, branch.y + 16)}
                      fill="none"
                      stroke={color}
                      strokeLinecap="round"
                      strokeWidth="2.5"
                    />
                    {branch.children.map((child) => (
                      <path
                        key={child.node.id}
                        d={curve(520, branch.y + 16, 620, child.y + 10)}
                        fill="none"
                        stroke={color}
                        strokeLinecap="round"
                        strokeWidth="1.75"
                      />
                    ))}
                    {branch.children.length === 0 ? (
                      <path
                        d={curve(520, branch.y + 16, 620, branch.y + 10)}
                        fill="none"
                        stroke={color}
                        strokeLinecap="round"
                        strokeWidth="1.75"
                      />
                    ) : null}
                  </g>
                )
              })}
            </svg>

            <button
              className="absolute z-20 cursor-pointer"
              style={{ left: 20, top: rootY - 28 }}
              type="button"
              onClick={() => setSelected(null)}
            >
              <div
                className="bg-[#0b1f3a] text-white px-5 py-3 shadow-lg flex items-center gap-2.5 border-2 border-slate-700/30 hover:scale-105 transition-transform max-w-[250px]"
                style={{ borderRadius: '9999px' }}
              >
                <MaterialIcon
                  name="folder_special"
                  className="text-[20px] text-amber-300 shrink-0"
                />
                <div className="flex flex-col text-left min-w-0">
                  <span className="font-bold text-[14px] leading-tight tracking-wide truncate">
                    {title}
                  </span>
                  {subtitle ? (
                    <span className="text-[10px] text-slate-300 font-mono truncate">
                      {subtitle}
                    </span>
                  ) : null}
                </div>
              </div>
            </button>

            {layout.branches.map((branch, index) => {
              const tone = palette[index % palette.length]
              const flagged = attentionIds?.has(branch.node.id) === true
              return (
                <div key={branch.node.id}>
                  <div
                    className="absolute z-10 flex items-center"
                    data-node-id={branch.node.id}
                    style={{ left: 340, top: branch.y }}
                  >
                    <button
                      className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 ${tone.bg} border ${tone.border} ${tone.text} shadow-sm font-semibold text-[13px] max-w-[190px] ${
                        selected === branch.node.id ||
                        focusId === branch.node.id
                          ? 'ring-2 ring-[#0b1f3a] ring-offset-2'
                          : ''
                      }`}
                      style={{ borderRadius: '9999px' }}
                      type="button"
                      onClick={() => setSelected(branch.node.id)}
                    >
                      <span
                        className="w-2 h-2 shrink-0"
                        style={{
                          borderRadius: '9999px',
                          backgroundColor: tone.color,
                        }}
                      />
                      <span className="truncate">{chipLabel(branch.node)}</span>
                      {flagged ? (
                        <MaterialIcon
                          name="star"
                          className="text-[14px] text-amber-500"
                        />
                      ) : null}
                    </button>
                    <CiteMark
                      active={focusId === branch.node.id}
                      n={citationOf?.get(branch.node.id)}
                      onCite={onCite ? () => onCite(branch.node.id) : undefined}
                    />
                  </div>
                  {branch.children.map((child) => {
                    const childFlagged =
                      attentionIds?.has(child.node.id) === true
                    const annex = child.node.nodeType === 'annex'
                    return (
                      <div
                        key={child.node.id}
                        className="absolute z-10 flex items-start"
                        data-node-id={child.node.id}
                        style={{ left: annex ? 860 : 620, top: child.y }}
                      >
                        {annex ? (
                          <button
                            className={`text-[11px] font-medium px-2 py-0.5 border flex items-center gap-1 max-w-[220px] ${annexTones[tone.tone]} ${
                              selected === child.node.id ||
                              focusId === child.node.id
                                ? 'ring-2 ring-[#0b1f3a] ring-offset-2'
                                : ''
                            }`}
                            style={{ borderRadius: '0.25rem' }}
                            type="button"
                            onClick={() => setSelected(child.node.id)}
                          >
                            <MaterialIcon
                              name="attachment"
                              className="text-[13px]"
                            />
                            <span className="truncate">
                              {chipLabel(child.node)}
                            </span>
                          </button>
                        ) : (
                          <ClauseButton
                            active={
                              selected === child.node.id ||
                              focusId === child.node.id
                            }
                            border={tone.link}
                            hover={tone.hover}
                            emphasize={childFlagged}
                            onClick={() => setSelected(child.node.id)}
                          >
                            {childFlagged ? (
                              <MaterialIcon
                                name="star"
                                className="text-[14px] text-amber-500"
                              />
                            ) : null}
                            {linkLabel(child.node)}
                          </ClauseButton>
                        )}
                        <CiteMark
                          active={focusId === child.node.id}
                          n={citationOf?.get(child.node.id)}
                          onCite={
                            onCite ? () => onCite(child.node.id) : undefined
                          }
                        />
                      </div>
                    )
                  })}
                  {branch.children.length === 0 ? (
                    <div
                      className="absolute z-10 max-w-[420px]"
                      style={{ left: 620, top: branch.y }}
                    >
                      <ClauseButton
                        active={selected === branch.node.id}
                        border={tone.link}
                        hover={tone.hover}
                        emphasize={flagged}
                        onClick={() => setSelected(branch.node.id)}
                      >
                        {linkLabel(branch.node)}
                      </ClauseButton>
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <PinnedToFrame frame={frame}>
        <ViewToolbar
          zoom={zoom}
          onExportData={exportData}
          onExportStructure={exportStructure}
          onFullscreen={toggleFullscreen}
          onRecenter={recenter}
          onZoom={updateZoom}
        />
      </PinnedToFrame>
    </div>
  )
}

function PinnedToFrame({
  frame,
  children,
}: {
  frame: HTMLElement | null
  children: ReactNode
}) {
  if (!frame) return children
  return createPortal(children, frame)
}

function ViewToolbar({
  zoom,
  onZoom,
  onRecenter,
  onFullscreen,
  onExportStructure,
  onExportData,
}: {
  zoom: number
  onZoom: (next: number) => void
  onRecenter: () => void
  onFullscreen: () => void
  onExportStructure: () => void
  onExportData: () => void
}) {
  const [open, setOpen] = useState(false)

  return (
    <div
      aria-label="Cấu hình hiển thị"
      className="absolute bottom-3 left-1/2 z-40 flex -translate-x-1/2 items-center justify-center px-20 py-3"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <div
        className={`origin-center overflow-hidden transition-all duration-200 ease-out ${
          open
            ? 'max-w-[56rem] translate-y-0 opacity-100'
            : 'pointer-events-none max-w-0 translate-y-1 opacity-0'
        }`}
      >
        <div
          className="flex items-center gap-2 whitespace-nowrap border border-slate-200/80 bg-white/95 px-3 py-1.5 text-slate-700 shadow-lg backdrop-blur"
          style={{ borderRadius: '9999px' }}
        >
          <div
            className="mr-1 flex items-center gap-1 bg-slate-100 px-2 py-1 text-xs font-medium"
            style={{ borderRadius: '9999px' }}
          >
            <span>Việt</span>
            <MaterialIcon name="keyboard_arrow_down" className="text-[14px]" />
          </div>
          <div className="h-4 w-px bg-slate-200" />
          <button
            className="flex h-7 w-7 items-center justify-center text-slate-600 transition-colors hover:bg-slate-100"
            style={{ borderRadius: '9999px' }}
            title="Thu nhỏ"
            type="button"
            onClick={() => onZoom(zoom - 0.1)}
          >
            <MaterialIcon name="remove" className="text-[18px]" />
          </button>
          <span className="min-w-[42px] px-1 text-center font-mono text-xs font-medium text-slate-800">
            {Math.round(zoom * 100)}%
          </span>
          <button
            className="flex h-7 w-7 items-center justify-center text-slate-600 transition-colors hover:bg-slate-100"
            style={{ borderRadius: '9999px' }}
            title="Phóng to"
            type="button"
            onClick={() => onZoom(zoom + 0.1)}
          >
            <MaterialIcon name="add" className="text-[18px]" />
          </button>
          <div className="h-4 w-px bg-slate-200" />
          <button
            className="flex h-7 w-7 items-center justify-center text-slate-600 transition-colors hover:bg-slate-100"
            style={{ borderRadius: '9999px' }}
            title="Căn giữa sơ đồ"
            type="button"
            onClick={onRecenter}
          >
            <MaterialIcon name="center_focus_strong" className="text-[16px]" />
          </button>
          <button
            className="flex h-7 w-7 items-center justify-center text-slate-600 transition-colors hover:bg-slate-100"
            style={{ borderRadius: '9999px' }}
            title="Toàn màn hình"
            type="button"
            onClick={onFullscreen}
          >
            <MaterialIcon name="fullscreen" className="text-[16px]" />
          </button>
          <div className="h-4 w-px bg-slate-200" />
          <button
            className="flex items-center gap-1.5 bg-primary px-3 py-1 text-xs font-semibold text-white shadow-sm transition-all hover:bg-primary-container"
            style={{ borderRadius: '9999px' }}
            type="button"
            onClick={onExportStructure}
          >
            <MaterialIcon name="account_tree" className="text-[15px]" />
            <span>Xuất cấu trúc cây</span>
          </button>
          <button
            className="flex items-center gap-1.5 border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-800 shadow-sm transition-all hover:bg-slate-50"
            style={{ borderRadius: '9999px' }}
            type="button"
            onClick={onExportData}
          >
            <MaterialIcon name="download" className="text-[15px]" />
            <span>Xuất dữ liệu</span>
          </button>
        </div>
      </div>
    </div>
  )
}

function CiteMark({
  n,
  active,
  onCite,
}: {
  n: number | undefined
  active: boolean
  onCite?: () => void
}) {
  if (!n || !onCite) return null
  return (
    <button
      className={`ml-1 inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full border px-1 text-[11px] font-semibold leading-none ${
        active
          ? 'border-[#0b1f3a] bg-[#0b1f3a] text-white'
          : 'border-slate-300 bg-white text-slate-700 hover:border-slate-500'
      }`}
      type="button"
      onClick={(event) => {
        event.stopPropagation()
        onCite()
      }}
    >
      {n}
    </button>
  )
}

function ClauseButton({
  active,
  border,
  hover,
  emphasize,
  onClick,
  children,
}: {
  active: boolean
  border: string
  hover: string
  emphasize?: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      className={`text-left text-xs pb-0.5 border-b-2 ${border} ${hover} cursor-pointer max-w-[280px] ${
        emphasize
          ? 'font-semibold text-slate-900'
          : 'font-medium text-slate-700'
      } ${active ? 'ring-2 ring-[#0b1f3a] ring-offset-2' : ''}`}
      type="button"
      onClick={onClick}
    >
      <span className="inline-flex items-start gap-1.5">{children}</span>
    </button>
  )
}
