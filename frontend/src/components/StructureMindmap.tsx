import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import type { ClauseNode } from '../api/structure'
import { citationNumbers } from '../structure/citations'
import {
  branchTones,
  countOf,
  dataDepth,
  downloadBlob,
  expandableIds,
  exportOutlineText,
  fullLabel,
  hasVisibleContent,
  nodeLabel,
  parentMap,
  visibleChildren,
  type BranchTone,
} from '../structure/display'
import { capToMaxLevels } from '../structure/tree'
import { MaterialIcon } from './icons'

/*
 * Sơ đồ tư duy theo kiểu NotebookLM:
 * - Cây ngang, gốc bên trái, mỗi nút là một hộp bo góc mang màu nhánh.
 * - Mỗi nút có con mang một nút tròn mũi tên ở mép phải để mở / thu riêng.
 * - Kéo nền để di chuyển, cuộn để thu phóng, nút +/−/vừa khung ở góc dưới.
 */

const tones = branchTones

const rootTone: BranchTone = {
  line: '#475569',
  bg: '#0b1f3a',
  bgSoft: '#0b1f3a',
  border: '#0b1f3a',
  text: '#ffffff',
}

const FONT_FAMILY = "'IBM Plex Sans', sans-serif"
const NODE_FONT = `500 13px ${FONT_FAMILY}`
const ROOT_FONT = `700 14px ${FONT_FAMILY}`
const NODE_LINE = 18
const ROOT_LINE = 20
const NODE_PAD_X = 12
const NODE_PAD_Y = 8
const ROOT_PAD_X = 16
const ROOT_PAD_Y = 10
const NODE_TEXT_MAX = 220
const ROOT_TEXT_MAX = 200
const NODE_MIN_WIDTH = 96
const MAX_LINES = 3
const GAP_X = 64
const GAP_Y = 10
const BRANCH_GAP_Y = 20
/** Cây dọc: hộp hẹp hơn để xếp nhiều anh em cạnh nhau. */
const NODE_TEXT_MAX_V = 170
const LEVEL_GAP_Y = 56
const SIBLING_GAP_X = 14
const BRANCH_GAP_X = 32
const TOGGLE = 22
const MARGIN = 40
const MIN_ZOOM = 0.2
const MAX_ZOOM = 2.5
const FIT_PAD = 48

// ---------------------------------------------------------------------------
// Đo chữ và xuống dòng
// ---------------------------------------------------------------------------

let measureCtx: CanvasRenderingContext2D | null | undefined

function textWidth(text: string, font: string) {
  if (measureCtx === undefined) {
    measureCtx =
      typeof document === 'undefined'
        ? null
        : document.createElement('canvas').getContext('2d')
  }
  if (!measureCtx) return text.length * 7
  measureCtx.font = font
  return measureCtx.measureText(text).width
}

function ellipsize(text: string, font: string, max: number) {
  if (textWidth(text, font) <= max) return text
  let next = text
  while (next.length > 1 && textWidth(`${next}…`, font) > max) {
    next = next.slice(0, -1)
  }
  return `${next.trimEnd()}…`
}

function wrapText(text: string, font: string, max: number, maxLines: number) {
  const words = text.replace(/\s+/g, ' ').trim().split(' ')
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    const probe = current ? `${current} ${word}` : word
    if (!current || textWidth(probe, font) <= max) {
      current = probe
    } else {
      lines.push(current)
      current = word
    }
  }
  if (current) lines.push(current)
  if (lines.length > maxLines) {
    const rest = lines.slice(maxLines - 1).join(' ')
    lines.length = maxLines - 1
    lines.push(rest)
  }
  return lines.map((line) => ellipsize(line, font, max))
}

// ---------------------------------------------------------------------------
// Bố cục cây: ngang (gốc trái, nhánh sang phải) hoặc dọc (gốc trên, xoè xuống)
// ---------------------------------------------------------------------------

export type TreeOrientation = 'horizontal' | 'vertical'

type Box = {
  id: string
  node: ClauseNode | null
  depth: number
  branch: number
  lines: string[]
  x: number
  y: number
  width: number
  height: number
  /** Bề rộng cả nhánh con đang mở theo trục xếp anh em (dọc khi cây ngang, ngang khi cây dọc). */
  span: number
  expandable: boolean
  open: boolean
  flagged: boolean
  children: Box[]
}

type Layout = {
  root: Box
  boxes: Box[]
  byId: Map<string, Box>
  width: number
  height: number
  levels: number
}

function gapFor(depth: number, orientation: TreeOrientation) {
  if (orientation === 'vertical') {
    return depth <= 1 ? BRANCH_GAP_X : SIBLING_GAP_X
  }
  return depth <= 1 ? BRANCH_GAP_Y : GAP_Y
}

/** Kích thước hộp theo trục xếp anh em. */
function extentOf(box: Box, orientation: TreeOrientation) {
  return orientation === 'vertical' ? box.width : box.height
}

function buildLayout(
  title: string,
  nodes: ClauseNode[],
  expanded: ReadonlySet<string>,
  rootOpen: boolean,
  attentionIds: ReadonlySet<string> | undefined,
  orientation: TreeOrientation,
): Layout {
  const boxes: Box[] = []
  const byId = new Map<string, Box>()
  const vertical = orientation === 'vertical'
  let levels = 0
  /** Cây dọc: chiều cao hàng theo cấp = hộp cao nhất của cấp đó. */
  const rowHeights: number[] = []

  function measure(node: ClauseNode, depth: number, branch: number): Box {
    levels = Math.max(levels, depth)
    const flagged = attentionIds?.has(node.id) === true
    const lines = wrapText(
      nodeLabel(node),
      NODE_FONT,
      vertical ? NODE_TEXT_MAX_V : NODE_TEXT_MAX,
      MAX_LINES,
    )
    const textW = Math.max(
      0,
      ...lines.map((line) => textWidth(line, NODE_FONT)),
    )
    const width = Math.max(
      NODE_MIN_WIDTH,
      Math.ceil(textW) + 2 + NODE_PAD_X * 2 + (flagged ? 22 : 0),
    )
    const height = Math.max(1, lines.length) * NODE_LINE + NODE_PAD_Y * 2
    const kids = visibleChildren(node)
    const expandable = kids.length > 0
    const open = expandable && expanded.has(node.id)
    const box: Box = {
      id: node.id,
      node,
      depth,
      branch,
      lines,
      x: 0,
      y: 0,
      width,
      height,
      span: 0,
      expandable,
      open,
      flagged,
      children: [],
    }
    box.span = extentOf(box, orientation)
    rowHeights[depth] = Math.max(rowHeights[depth] ?? 0, height)
    if (open) {
      box.children = kids.map((kid) => measure(kid, depth + 1, branch))
      const gap = gapFor(depth + 1, orientation)
      const childrenSpan =
        box.children.reduce((sum, kid) => sum + kid.span, 0) +
        gap * (box.children.length - 1)
      box.span = Math.max(box.span, childrenSpan)
    }
    boxes.push(box)
    byId.set(box.id, box)
    return box
  }

  const rootLines = wrapText(
    title.trim() || 'Hợp đồng',
    ROOT_FONT,
    ROOT_TEXT_MAX,
    2,
  )
  const rootTextW = Math.max(
    0,
    ...rootLines.map((line) => textWidth(line, ROOT_FONT)),
  )
  const roots = nodes.filter(hasVisibleContent)
  const root: Box = {
    id: '__root__',
    node: null,
    depth: 0,
    branch: -1,
    lines: rootLines,
    x: 0,
    y: 0,
    width: Math.max(140, Math.ceil(rootTextW) + 2 + ROOT_PAD_X * 2),
    height: Math.max(1, rootLines.length) * ROOT_LINE + ROOT_PAD_Y * 2,
    span: 0,
    expandable: roots.length > 0,
    open: rootOpen && roots.length > 0,
    flagged: false,
    children: [],
  }
  root.span = extentOf(root, orientation)
  rowHeights[0] = root.height
  if (root.open) {
    root.children = roots.map((node, index) =>
      measure(node, 1, index % tones.length),
    )
    const childrenSpan =
      root.children.reduce((sum, kid) => sum + kid.span, 0) +
      gapFor(1, orientation) * (root.children.length - 1)
    root.span = Math.max(root.span, childrenSpan)
  }
  boxes.push(root)
  byId.set(root.id, root)

  // Cây ngang: x theo cấp (cha + khe), y xếp anh em. Cây dọc: ngược lại,
  // y theo hàng cấp (cao bằng hộp cao nhất cấp đó), x xếp anh em.
  const rowTops: number[] = []
  let cursorY = MARGIN
  rowHeights.forEach((rowHeight, depth) => {
    rowTops[depth] = cursorY
    cursorY += rowHeight + LEVEL_GAP_Y
  })

  let maxRight = 0
  let maxBottom = 0
  function place(box: Box, along: number, start: number) {
    // along: toạ độ theo trục cấp (x khi ngang, y khi dọc);
    // start: mép đầu của khoảng span theo trục anh em.
    if (vertical) {
      box.y = rowTops[box.depth] ?? along
    } else {
      box.x = along
    }
    const gap = gapFor(box.depth + 1, orientation)
    if (box.children.length === 0) {
      if (vertical) box.x = start
      else box.y = start
    } else {
      const childrenSpan =
        box.children.reduce((sum, kid) => sum + kid.span, 0) +
        gap * (box.children.length - 1)
      let cursor = start + (box.span - childrenSpan) / 2
      const nextAlong = vertical
        ? (rowTops[box.depth + 1] ?? along)
        : along + box.width + GAP_X
      for (const kid of box.children) {
        place(kid, nextAlong, cursor)
        cursor += kid.span + gap
      }
      const first = box.children[0]
      const last = box.children[box.children.length - 1]
      if (vertical) {
        const mid = (first.x + first.width / 2 + last.x + last.width / 2) / 2
        box.x = Math.min(
          Math.max(start, mid - box.width / 2),
          start + box.span - box.width,
        )
      } else {
        const mid = (first.y + first.height / 2 + last.y + last.height / 2) / 2
        box.y = Math.min(
          Math.max(start, mid - box.height / 2),
          start + box.span - box.height,
        )
      }
    }
    maxRight = Math.max(maxRight, box.x + box.width)
    maxBottom = Math.max(maxBottom, box.y + box.height)
  }
  place(root, MARGIN, MARGIN)

  return {
    root,
    boxes,
    byId,
    width: maxRight + TOGGLE + MARGIN,
    height: maxBottom + TOGGLE + MARGIN,
    levels,
  }
}

type Edge = { key: string; d: string; color: string }

/** Hai đầu đường nối: mép phải cha → mép trái con (ngang) hoặc đáy cha → đỉnh con (dọc). */
function edgeEnds(parent: Box, child: Box, orientation: TreeOrientation) {
  if (orientation === 'vertical') {
    return {
      x1: parent.x + parent.width / 2,
      y1: parent.y + parent.height,
      x2: child.x + child.width / 2,
      y2: child.y,
    }
  }
  return {
    x1: parent.x + parent.width,
    y1: parent.y + parent.height / 2,
    x2: child.x,
    y2: child.y + child.height / 2,
  }
}

function edgeControls(
  ends: ReturnType<typeof edgeEnds>,
  orientation: TreeOrientation,
) {
  const { x1, y1, x2, y2 } = ends
  if (orientation === 'vertical') {
    const mid = (y1 + y2) / 2
    return { c1x: x1, c1y: mid, c2x: x2, c2y: mid }
  }
  const mid = (x1 + x2) / 2
  return { c1x: mid, c1y: y1, c2x: mid, c2y: y2 }
}

function edgePath(parent: Box, child: Box, orientation: TreeOrientation) {
  const ends = edgeEnds(parent, child, orientation)
  const c = edgeControls(ends, orientation)
  return `M ${ends.x1} ${ends.y1} C ${c.c1x} ${c.c1y}, ${c.c2x} ${c.c2y}, ${ends.x2} ${ends.y2}`
}

function toneOf(box: Box) {
  return box.depth === 0 ? rootTone : tones[box.branch % tones.length]
}

function layoutEdges(layout: Layout, orientation: TreeOrientation): Edge[] {
  const edges: Edge[] = []
  for (const box of layout.boxes) {
    for (const child of box.children) {
      edges.push({
        key: `${box.id}->${child.id}`,
        d: edgePath(box, child, orientation),
        color: toneOf(child).line,
      })
    }
  }
  return edges
}

// ---------------------------------------------------------------------------
// Xuất PDF từ cùng bố cục đang hiển thị
// ---------------------------------------------------------------------------

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
  layout,
  orientation,
  heading,
  caption,
  numbers,
}: {
  layout: Layout
  orientation: TreeOrientation
  heading: string
  caption: string
  numbers?: ReadonlyMap<string, number>
}) {
  const HEADER = 52
  const pageWidth = Math.max(720, layout.width)
  const pageHeight = HEADER + layout.height
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
  ctx.fillRect(0, 0, pageWidth, HEADER)
  ctx.strokeStyle = '#e2e8f0'
  ctx.beginPath()
  ctx.moveTo(0, HEADER)
  ctx.lineTo(pageWidth, HEADER)
  ctx.stroke()
  ctx.fillStyle = '#0f172a'
  ctx.font = `600 15px ${FONT_FAMILY}`
  ctx.fillText(heading, 24, 32)
  ctx.font = `500 11px ${FONT_FAMILY}`
  const captionWidth = ctx.measureText(caption).width + 20
  roundRect(ctx, pageWidth - 24 - captionWidth, 16, captionWidth, 22, 11)
  ctx.fillStyle = '#eef2f7'
  ctx.fill()
  ctx.fillStyle = '#64748b'
  ctx.fillText(caption, pageWidth - 14 - captionWidth, 31)

  ctx.save()
  ctx.translate(0, HEADER)
  ctx.lineCap = 'round'
  for (const box of layout.boxes) {
    for (const child of box.children) {
      const ends = edgeEnds(box, child, orientation)
      const c = edgeControls(ends, orientation)
      ctx.beginPath()
      ctx.moveTo(ends.x1, ends.y1)
      ctx.bezierCurveTo(c.c1x, c.c1y, c.c2x, c.c2y, ends.x2, ends.y2)
      ctx.strokeStyle = toneOf(child).line
      ctx.lineWidth = 1.6
      ctx.stroke()
    }
  }

  ctx.textBaseline = 'middle'
  for (const box of layout.boxes) {
    const tone = toneOf(box)
    const isRoot = box.depth === 0
    roundRect(ctx, box.x, box.y, box.width, box.height, isRoot ? 12 : 8)
    ctx.fillStyle = isRoot ? tone.bg : box.depth === 1 ? tone.bg : tone.bgSoft
    ctx.fill()
    ctx.lineWidth = 1
    ctx.strokeStyle = tone.border
    ctx.stroke()
    ctx.fillStyle = tone.text
    ctx.font = isRoot ? ROOT_FONT : NODE_FONT
    const lineH = isRoot ? ROOT_LINE : NODE_LINE
    const padX = isRoot ? ROOT_PAD_X : NODE_PAD_X
    const padY = isRoot ? ROOT_PAD_Y : NODE_PAD_Y
    box.lines.forEach((line, index) => {
      ctx.fillText(line, box.x + padX, box.y + padY + index * lineH + lineH / 2)
    })
    if (box.flagged) {
      ctx.fillStyle = '#f59e0b'
      ctx.font = `600 13px ${FONT_FAMILY}`
      ctx.fillText(
        '★',
        box.x + box.width - padX - 10,
        box.y + padY + NODE_LINE / 2,
      )
    }
    const n = box.node ? numbers?.get(box.node.id) : undefined
    if (n) {
      const badge = String(n)
      ctx.font = `600 10px ${FONT_FAMILY}`
      const badgeWidth = Math.max(16, ctx.measureText(badge).width + 8)
      roundRect(ctx, box.x - 6, box.y - 8, badgeWidth, 16, 8)
      ctx.fillStyle = '#ffffff'
      ctx.fill()
      ctx.strokeStyle = tone.line
      ctx.stroke()
      ctx.fillStyle = '#0f172a'
      ctx.fillText(
        badge,
        box.x - 6 + (badgeWidth - ctx.measureText(badge).width) / 2,
        box.y,
      )
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

// ---------------------------------------------------------------------------
// Thành phần chính
// ---------------------------------------------------------------------------

type View = { x: number; y: number; scale: number }

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

export function StructureMindmap({
  title,
  subtitle,
  nodes,
  attentionIds,
  citationOf,
  focusId,
  orientation = 'horizontal',
  onCite,
}: {
  title: string
  subtitle?: string | null
  nodes: ClauseNode[]
  attentionIds?: ReadonlySet<string>
  citationOf?: ReadonlyMap<string, number>
  focusId?: string | null
  /** 'horizontal': sơ đồ tư duy gốc trái; 'vertical': cây từ trên xuống. */
  orientation?: TreeOrientation
  onCite?: (id: string) => void
}) {
  const vertical = orientation === 'vertical'
  const heading = vertical ? 'Cây từ trên xuống' : 'Sơ đồ tư duy'
  const source = useMemo(() => capToMaxLevels(nodes), [nodes])
  const parents = useMemo(() => parentMap(source), [source])
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set())
  const [rootOpen, setRootOpen] = useState(true)
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<View>({ x: MARGIN, y: MARGIN, scale: 1 })
  const [dragging, setDragging] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const shellRef = useRef<HTMLDivElement | null>(null)
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const dragRef = useRef<{
    pointerId: number
    startX: number
    startY: number
    originX: number
    originY: number
  } | null>(null)
  /** Tự căn vừa khung cho tới khi người dùng tự kéo / thu phóng. */
  const autoFit = useRef(true)
  const pendingFocus = useRef<string | null>(null)
  /** Tăng khi font web tải xong để đo lại chữ; đo sớm bằng font thay thế sẽ lệch. */
  const [fontsVersion, setFontsVersion] = useState(0)

  useEffect(() => {
    const fonts = document.fonts
    if (!fonts) return
    let alive = true
    const bump = () => {
      if (alive) setFontsVersion((version) => version + 1)
    }
    void fonts.ready.then(bump)
    fonts.addEventListener('loadingdone', bump)
    return () => {
      alive = false
      fonts.removeEventListener('loadingdone', bump)
    }
  }, [])

  const layout = useMemo(() => {
    // Chỉ để ép đo lại chữ khi font web tải xong.
    void fontsVersion
    return buildLayout(
      title,
      source,
      expanded,
      rootOpen,
      attentionIds,
      orientation,
    )
  }, [
    title,
    source,
    expanded,
    rootOpen,
    attentionIds,
    orientation,
    fontsVersion,
  ])
  const edges = useMemo(
    () => layoutEdges(layout, orientation),
    [layout, orientation],
  )
  const numbers = useMemo(
    () => citationOf ?? citationNumbers(nodes),
    [citationOf, nodes],
  )
  const articleCount = countOf(nodes, 'article') || nodes.length
  const annexCount = countOf(nodes, 'annex')
  const maxDepth = useMemo(() => dataDepth(source), [source])
  const caption = `${layout.levels}/${maxDepth} cấp • ${articleCount} điều khoản${
    annexCount > 0 ? ` • ${annexCount} phụ lục` : ''
  }`

  // Dữ liệu đổi (đổi loại cấu trúc, tải lại): về trạng thái mặc định.
  useEffect(() => {
    setExpanded(new Set())
    setRootOpen(true)
    setSelected(null)
    autoFit.current = true
  }, [source])

  const fitToView = useCallback(() => {
    const el = viewportRef.current
    if (!el) return
    const w = el.clientWidth
    const h = el.clientHeight
    if (!w || !h) return
    const scale = clamp(
      Math.min(1, (w - FIT_PAD) / layout.width, (h - FIT_PAD) / layout.height),
      MIN_ZOOM,
      MAX_ZOOM,
    )
    setView({
      scale,
      x: (w - layout.width * scale) / 2,
      y: (h - layout.height * scale) / 2,
    })
  }, [layout.width, layout.height])

  useLayoutEffect(() => {
    if (autoFit.current) fitToView()
  }, [fitToView])

  // Khung đổi kích thước (toàn màn hình, thu bảng bên) → căn lại nếu chưa ai chạm.
  useEffect(() => {
    const el = viewportRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => {
      if (autoFit.current) fitToView()
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [fitToView])

  useEffect(() => {
    function onChange() {
      setFullscreen(Boolean(document.fullscreenElement))
    }
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const zoomAt = useCallback((px: number, py: number, factor: number) => {
    autoFit.current = false
    setView((current) => {
      const scale = clamp(current.scale * factor, MIN_ZOOM, MAX_ZOOM)
      const ratio = scale / current.scale
      return {
        scale,
        x: px - (px - current.x) * ratio,
        y: py - (py - current.y) * ratio,
      }
    })
  }, [])

  // Cuộn để thu phóng quanh con trỏ (React gắn onWheel dạng passive nên dùng listener thô).
  useEffect(() => {
    const el = viewportRef.current
    if (!el) return
    function onWheel(event: WheelEvent) {
      event.preventDefault()
      if (!el) return
      const rect = el.getBoundingClientRect()
      const delta = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY
      zoomAt(
        event.clientX - rect.left,
        event.clientY - rect.top,
        Math.exp(-delta * 0.0012),
      )
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomAt])

  function zoomBy(factor: number) {
    const el = viewportRef.current
    if (!el) return
    zoomAt(el.clientWidth / 2, el.clientHeight / 2, factor)
  }

  // Trích dẫn từ nơi khác: mở các cấp cha rồi kéo nút vào khung nếu đang khuất.
  useEffect(() => {
    if (!focusId) return
    pendingFocus.current = focusId
    setRootOpen(true)
    setExpanded((current) => {
      const next = new Set(current)
      let changed = false
      let cursor = parents.get(focusId) ?? null
      while (cursor) {
        if (!next.has(cursor)) {
          next.add(cursor)
          changed = true
        }
        cursor = parents.get(cursor) ?? null
      }
      return changed ? next : current
    })
  }, [focusId, parents])

  useLayoutEffect(() => {
    const id = pendingFocus.current
    if (!id) return
    const box = layout.byId.get(id)
    const el = viewportRef.current
    if (!box || !el) return
    pendingFocus.current = null
    const w = el.clientWidth
    const h = el.clientHeight
    setView((current) => {
      const left = current.x + box.x * current.scale
      const top = current.y + box.y * current.scale
      const right = left + box.width * current.scale
      const bottom = top + box.height * current.scale
      if (left >= 0 && top >= 0 && right <= w && bottom <= h) return current
      autoFit.current = false
      return {
        ...current,
        x: w / 2 - (box.x + box.width / 2) * current.scale,
        y: h / 2 - (box.y + box.height / 2) * current.scale,
      }
    })
  }, [layout])

  function toggleNode(id: string) {
    if (id === layout.root.id) {
      setRootOpen((open) => !open)
      return
    }
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function expandAll() {
    setRootOpen(true)
    setExpanded(expandableIds(source))
  }

  function collapseAll() {
    setRootOpen(true)
    setExpanded(new Set())
  }

  function pickNode(id: string) {
    setSelected(id)
    onCite?.(id)
  }

  function startDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    if ((event.target as HTMLElement).closest('button')) return
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: view.x,
      originY: view.y,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
    setDragging(true)
  }

  function moveDrag(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    autoFit.current = false
    const dx = event.clientX - drag.startX
    const dy = event.clientY - drag.startY
    setView((current) => ({
      ...current,
      x: drag.originX + dx,
      y: drag.originY + dy,
    }))
  }

  function endDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragRef.current?.pointerId !== event.pointerId) return
    dragRef.current = null
    setDragging(false)
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

  async function exportStructure() {
    const blob = await mindmapPdf({
      layout,
      orientation,
      heading: `${heading} cấu trúc hợp đồng`,
      caption: subtitle ? `${subtitle} • ${caption}` : caption,
      numbers,
    })
    downloadBlob(vertical ? 'cay-cau-truc.pdf' : 'so-do-tu-duy.pdf', blob)
  }

  function exportData() {
    exportOutlineText(title, nodes)
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
      ref={shellRef}
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-outline-variant/20 bg-surface-container-lowest shadow-sm"
    >
      <div className="z-10 flex items-center justify-between gap-3 border-b border-outline-variant/20 bg-surface-container-low/60 px-4 py-2">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex min-w-0 items-center gap-2 font-title-sm text-title-sm text-primary">
            <MaterialIcon
              name={vertical ? 'lan' : 'account_tree'}
              className="shrink-0 text-[20px] text-primary"
            />
            <span className="truncate font-semibold">{heading}</span>
          </div>
          <span
            className="hidden shrink-0 bg-surface-container px-2.5 py-0.5 font-mono text-[11px] text-secondary xl:inline"
            style={{ borderRadius: '9999px' }}
          >
            {caption}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <IconButton
            icon="unfold_more"
            label="Mở rộng tất cả"
            onClick={expandAll}
          />
          <IconButton
            icon="unfold_less"
            label="Thu gọn tất cả"
            onClick={collapseAll}
          />
          <span className="mx-1 h-4 w-px bg-outline-variant/40" />
          <IconButton
            icon="picture_as_pdf"
            label="Xuất sơ đồ (PDF)"
            onClick={() => void exportStructure()}
          />
          <IconButton
            icon="download"
            label="Xuất dữ liệu (TXT)"
            onClick={exportData}
          />
          <IconButton
            icon={fullscreen ? 'fullscreen_exit' : 'fullscreen'}
            label={fullscreen ? 'Thoát toàn màn hình' : 'Toàn màn hình'}
            onClick={toggleFullscreen}
          />
        </div>
      </div>

      <div
        ref={viewportRef}
        className={`relative min-h-0 flex-1 touch-none overflow-hidden bg-[#fafbff] ${
          dragging ? 'cursor-grabbing' : 'cursor-grab'
        }`}
        onPointerCancel={endDrag}
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
      >
        <div
          className="absolute left-0 top-0 origin-top-left select-none"
          style={{
            width: layout.width,
            height: layout.height,
            transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
          }}
        >
          <svg
            className="pointer-events-none absolute inset-0"
            height={layout.height}
            width={layout.width}
            xmlns="http://www.w3.org/2000/svg"
          >
            {edges.map((edge) => (
              <path
                key={edge.key}
                d={edge.d}
                fill="none"
                stroke={edge.color}
                strokeLinecap="round"
                strokeWidth={1.6}
              />
            ))}
          </svg>
          {layout.boxes.map((box) => (
            <NodeBox
              key={box.id}
              active={
                box.node !== null && (selected === box.id || focusId === box.id)
              }
              box={box}
              cite={box.node ? numbers.get(box.node.id) : undefined}
              orientation={orientation}
              onPick={
                box.node ? () => pickNode(box.id) : () => setSelected(null)
              }
              onToggle={() => toggleNode(box.id)}
            />
          ))}
        </div>

        <div
          className="absolute bottom-3 right-3 z-20 flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-md"
          aria-label="Thu phóng"
        >
          <IconButton
            icon="add"
            label="Phóng to"
            square
            onClick={() => zoomBy(1.25)}
          />
          <span className="h-px w-full bg-slate-200" />
          <IconButton
            icon="remove"
            label="Thu nhỏ"
            square
            onClick={() => zoomBy(0.8)}
          />
          <span className="h-px w-full bg-slate-200" />
          <IconButton
            icon="fit_screen"
            label="Vừa khung"
            square
            onClick={() => {
              autoFit.current = true
              fitToView()
            }}
          />
        </div>
        <p className="pointer-events-none absolute bottom-3 left-3 z-20 select-none text-[11px] text-slate-400">
          Kéo để di chuyển • Cuộn để thu phóng • Bấm mũi tên để mở nhánh
        </p>
      </div>
    </div>
  )
}

function NodeBox({
  box,
  active,
  cite,
  orientation,
  onPick,
  onToggle,
}: {
  box: Box
  active: boolean
  cite: number | undefined
  orientation: TreeOrientation
  onPick: () => void
  onToggle: () => void
}) {
  const tone = toneOf(box)
  const isRoot = box.depth === 0
  const vertical = orientation === 'vertical'
  const background = isRoot || box.depth === 1 ? tone.bg : tone.bgSoft
  return (
    <div
      className="absolute"
      data-node-id={box.node ? box.id : undefined}
      style={{ left: box.x, top: box.y, width: box.width, height: box.height }}
    >
      <button
        className={`block h-full w-full text-left shadow-sm transition-shadow hover:shadow-md ${
          active ? 'ring-2 ring-[#0b1f3a] ring-offset-1' : ''
        }`}
        style={{
          backgroundColor: background,
          border: `1px solid ${tone.border}`,
          borderRadius: isRoot ? 12 : 8,
          color: tone.text,
          fontFamily: FONT_FAMILY,
          fontSize: isRoot ? 14 : 13,
          fontWeight: isRoot ? 700 : 500,
          lineHeight: `${isRoot ? ROOT_LINE : NODE_LINE}px`,
          padding: isRoot
            ? `${ROOT_PAD_Y - 1}px ${ROOT_PAD_X - 1}px`
            : `${NODE_PAD_Y - 1}px ${NODE_PAD_X - 1}px`,
        }}
        title={box.node ? fullLabel(box.node) : undefined}
        type="button"
        onClick={onPick}
      >
        <span className="flex items-start gap-1.5">
          <span className="min-w-0 flex-1">
            {box.lines.map((line, index) => (
              <span
                key={index}
                className="block overflow-hidden text-ellipsis whitespace-nowrap"
              >
                {line}
              </span>
            ))}
          </span>
          {box.flagged ? (
            <span
              className="flex shrink-0 items-center justify-center overflow-hidden text-amber-500"
              style={{ width: 16, height: NODE_LINE, fontSize: 15 }}
              title="Có chỗ cần kiểm tra"
            >
              <MaterialIcon name="star" className="!text-[15px]" />
            </span>
          ) : null}
        </span>
      </button>
      {cite ? (
        <span
          className="pointer-events-none absolute -left-1.5 -top-2 inline-flex h-4 min-w-4 items-center justify-center rounded-full border bg-white px-1 text-[10px] font-semibold leading-none text-slate-800"
          style={{ borderColor: tone.line }}
        >
          {cite}
        </span>
      ) : null}
      {box.expandable ? (
        <button
          aria-expanded={box.open}
          aria-label={box.open ? 'Thu nhánh' : 'Mở nhánh'}
          className={`absolute flex items-center justify-center rounded-full border bg-white shadow-sm transition-colors hover:bg-slate-50 ${
            vertical ? 'left-1/2 -translate-x-1/2' : 'top-1/2 -translate-y-1/2'
          }`}
          style={{
            ...(vertical ? { bottom: -TOGGLE / 2 } : { right: -TOGGLE / 2 }),
            width: TOGGLE,
            height: TOGGLE,
            borderColor: tone.line,
            color: tone.line,
          }}
          title={box.open ? 'Thu nhánh' : 'Mở nhánh'}
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onToggle()
          }}
        >
          <MaterialIcon
            name={
              vertical
                ? box.open
                  ? 'expand_less'
                  : 'expand_more'
                : box.open
                  ? 'chevron_left'
                  : 'chevron_right'
            }
            className="text-[16px]"
          />
        </button>
      ) : null}
    </div>
  )
}

function IconButton({
  icon,
  label,
  square,
  onClick,
}: {
  icon: string
  label: string
  square?: boolean
  onClick: () => void
}) {
  return (
    <button
      aria-label={label}
      className={`flex items-center justify-center text-slate-600 transition-colors hover:bg-slate-200/70 hover:text-slate-900 ${
        square ? 'h-9 w-9' : 'h-8 w-8 rounded-full'
      }`}
      title={label}
      type="button"
      onClick={onClick}
    >
      <MaterialIcon name={icon} className="text-[20px]" />
    </button>
  )
}
