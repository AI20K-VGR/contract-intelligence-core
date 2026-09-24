import {
  STRUCTURE_MODE_KEY,
  parseStructureMode,
  type OcrLine,
  type StructureMode,
} from '../structure/types'
import { ApiError, apiFetch, getJson } from './client'
import { patchDossier } from './dossiers'

export type StructureDocument = {
  id: string
  role: string
  filename: string
  pageCount: number
}

export type DossierStructure = {
  id: string
  name: string
  latestJobStatus: string | null
  documents: StructureDocument[]
  metadata: Record<string, unknown> | null
  /** metadata.structure_mode do người dùng chọn khi tải lên. */
  structureMode: StructureMode | null
}

export type DocumentPage = {
  id: string
  pageNo: number
  widthPt: number
  heightPt: number
}

export type ClauseRegion = {
  pageNo: number
  /** [x1, y1, x2, y2] chuẩn hóa 0..1 theo trang. */
  bbox: [number, number, number, number]
}

export type ClauseNode = {
  id: string
  nodeType: string
  label: string
  number: string | null
  title: string | null
  text: string
  pageStart: number
  pageEnd: number
  confidence: number | null
  regions: ClauseRegion[]
  children: ClauseNode[]
}

export type ReviewSpot = {
  id: string
  topic: string
  rationale: string
  severity: string
  clauseIds: string[]
  sides: { label: string; value: string; quote: string }[]
}

const DONE_STATUSES = new Set([
  'extracted',
  'pending_review',
  'reviewed',
  'approved',
])

export function isOcrComplete(status: string | null) {
  return status !== null && DONE_STATUSES.has(status)
}

export function countClauses(nodes: ClauseNode[]): number {
  return nodes.reduce(
    (total, node) => total + 1 + countClauses(node.children),
    0,
  )
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function asString(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function asClause(value: unknown): ClauseNode | null {
  const row = asRecord(value)
  if (!row) return null
  const id = asString(row.id)
  if (!id) return null
  const children = Array.isArray(row.children)
    ? row.children
        .map(asClause)
        .filter((node): node is ClauseNode => node !== null)
    : []
  return {
    id,
    nodeType: asString(row.node_type) || 'clause',
    label: asString(row.label),
    number: typeof row.number === 'string' ? row.number : null,
    title: typeof row.title === 'string' ? row.title : null,
    text: asString(row.text),
    pageStart: asNumber(row.page_start),
    pageEnd: asNumber(row.page_end),
    confidence:
      typeof row.confidence === 'number' && Number.isFinite(row.confidence)
        ? row.confidence
        : null,
    regions: asRegions(row.regions),
    children,
  }
}

function asRegions(value: unknown): ClauseRegion[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    const row = asRecord(item)
    if (!row) return []
    const bbox = asBBox(row.bbox, 0, 0)
    if (!bbox) return []
    const pageNo = asNumber(row.page_no)
    return [{ pageNo: pageNo > 0 ? pageNo : 1, bbox }]
  })
}

export function contractDocument(detail: DossierStructure) {
  return (
    detail.documents.find(
      (document) => document.role.toLowerCase() === 'contract',
    ) ??
    detail.documents[0] ??
    null
  )
}

export async function getDossierStructure(
  dossierId: string,
  signal?: AbortSignal,
) {
  const data = await getJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}`,
    { signal },
  )
  const row = asRecord(data)
  const id = asString(row?.id)
  if (!row || !id) {
    throw new Error('Backend không trả chi tiết hồ sơ.')
  }
  const documents = Array.isArray(row.documents)
    ? row.documents.flatMap((item) => {
        const document = asRecord(item)
        const documentId = asString(document?.id)
        if (!document || !documentId) return []
        return [
          {
            id: documentId,
            role: asString(document.role),
            filename: asString(document.filename) || 'Tài liệu',
            pageCount: asNumber(document.page_count),
          },
        ]
      })
    : []
  const metadata = asRecord(row.metadata)
  return {
    id,
    name: asString(row.name) || 'Hồ sơ chưa đặt tên',
    latestJobStatus:
      typeof row.latest_job_status === 'string' ? row.latest_job_status : null,
    documents,
    metadata,
    structureMode: parseStructureMode(metadata?.[STRUCTURE_MODE_KEY]),
  } satisfies DossierStructure
}

/**
 * PATCH thay toàn bộ metadata, nên gộp với metadata hiện có rồi mới ghi.
 */
export async function saveStructureMode(
  dossierId: string,
  current: Record<string, unknown> | null,
  mode: StructureMode,
) {
  await patchDossier(dossierId, {
    metadata: { ...(current ?? {}), [STRUCTURE_MODE_KEY]: mode },
  })
}

function asBBox(
  value: unknown,
  widthPt: number,
  heightPt: number,
): [number, number, number, number] | null {
  let raw: unknown = value
  if (typeof raw === 'string') {
    try {
      raw = JSON.parse(raw) as unknown
    } catch {
      return null
    }
  }
  if (!Array.isArray(raw) || raw.length < 4) return null
  const box = raw.slice(0, 4).map(Number)
  if (box.some((item) => !Number.isFinite(item))) return null
  // AI1 trả bbox chuẩn hóa 0..1. Nếu gặp tọa độ điểm (pt) thì tự chuẩn hóa.
  if (box.some((item) => item > 1.5) && widthPt > 0 && heightPt > 0) {
    return [
      box[0] / widthPt,
      box[1] / heightPt,
      box[2] / widthPt,
      box[3] / heightPt,
    ]
  }
  return [box[0], box[1], box[2], box[3]]
}

const pdfCache = new Map<string, Uint8Array>()

export async function loadDocumentPdf(
  documentId: string,
  signal?: AbortSignal,
) {
  const cached = pdfCache.get(documentId)
  if (cached) return cached
  const response = await apiFetch(
    `/api/v1/documents/${encodeURIComponent(documentId)}/content`,
    { signal },
  )
  if (!response.ok) {
    throw new Error('Không tải được file hợp đồng.')
  }
  const bytes = new Uint8Array(await response.arrayBuffer())
  if (!signal?.aborted) pdfCache.set(documentId, bytes)
  return bytes
}

export async function loadPagePreview(
  documentId: string,
  pageNo: number,
  signal?: AbortSignal,
) {
  const response = await apiFetch(
    `/api/v1/documents/${encodeURIComponent(documentId)}/pages/${pageNo}/image?variant=preview`,
    { signal },
  )
  if (!response.ok) {
    throw new Error('Không tải được trang hợp đồng.')
  }
  return response.blob()
}

export async function listPages(documentId: string, signal?: AbortSignal) {
  const data = await getJson<unknown>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/pages`,
    { signal },
  )
  if (!Array.isArray(data)) return []
  return data
    .flatMap((item): DocumentPage[] => {
      const row = asRecord(item)
      const id = asString(row?.id)
      if (!row || !id) return []
      return [
        {
          id,
          pageNo: asNumber(row.page_no),
          widthPt: asNumber(row.width_pt),
          heightPt: asNumber(row.height_pt),
        },
      ]
    })
    .sort((a, b) => a.pageNo - b.pageNo)
}

export async function getPageLines(page: DocumentPage, signal?: AbortSignal) {
  const data = await getJson<unknown>(
    `/api/v1/pages/${encodeURIComponent(page.id)}`,
    { signal },
  )
  const row = asRecord(data)
  const rows = row?.ocr_lines
  if (!Array.isArray(rows)) return []
  return rows.flatMap((item, index): OcrLine[] => {
    const line = asRecord(item)
    if (!line) return []
    const text = asString(line.text)
    if (!text.trim()) return []
    return [
      {
        id: asString(line.id) || `${page.id}-${index}`,
        pageNo: page.pageNo,
        lineNo: asNumber(line.line_no) || index + 1,
        text,
        bbox: asBBox(line.bbox, page.widthPt, page.heightPt),
        pageWidth: page.widthPt,
        pageHeight: page.heightPt,
      },
    ]
  })
}

const PAGE_FETCH_BATCH = 4

/** Toàn bộ dòng OCR của tài liệu, theo thứ tự trang rồi thứ tự dòng. */
export async function loadDocumentLines(
  documentId: string,
  signal?: AbortSignal,
) {
  const pages = await listPages(documentId, signal)
  const lines: OcrLine[] = []
  for (let start = 0; start < pages.length; start += PAGE_FETCH_BATCH) {
    const batch = pages.slice(start, start + PAGE_FETCH_BATCH)
    const results = await Promise.all(
      batch.map((page) => getPageLines(page, signal)),
    )
    for (const result of results) lines.push(...result)
  }
  return lines
}

function snapshotText(value: unknown) {
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  const row = asRecord(value)
  if (!row) return ''
  return (
    asString(row.value) ||
    asString(row.text) ||
    asString(row.normalized_value) ||
    asString(row.raw_text)
  )
}

function asReviewSpot(value: unknown): ReviewSpot | null {
  const row = asRecord(value)
  const id = asString(row?.id)
  if (!row || !id) return null
  const sides = Array.isArray(row.sides)
    ? row.sides.flatMap((item) => {
        const side = asRecord(item)
        if (!side) return []
        const citation = asRecord(side.citation)
        return [
          {
            label:
              asString(side.document_role) || asString(side.side) || 'Nguồn',
            value: snapshotText(side.value_snapshot) || '—',
            quote: asString(citation?.quote),
          },
        ]
      })
    : []
  const clauseIds = Array.isArray(row.sides)
    ? row.sides.flatMap((item) => {
        const side = asRecord(item)
        const clauseId = asString(side?.clause_node_id)
        return clauseId ? [clauseId] : []
      })
    : []
  return {
    id,
    topic: asString(row.key_or_topic) || 'Nội dung cần kiểm tra',
    rationale: asString(row.rationale),
    severity: asString(row.severity),
    clauseIds,
    sides,
  }
}

export async function listReviewSpots(dossierId: string, signal?: AbortSignal) {
  const data = await getJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/conflicts?limit=100&offset=0`,
    { signal },
  )
  if (!Array.isArray(data)) return []
  return data
    .map(asReviewSpot)
    .filter((spot): spot is ReviewSpot => spot !== null)
}

export type DocumentTableCell = {
  row: number
  column: number
  rowSpan: number
  colSpan: number
  text: string
  header: boolean
}

export type DocumentTable = {
  id: string
  pageNo: number
  rows: number
  columns: number
  continued: boolean
  cells: DocumentTableCell[]
}

export async function listDocumentTables(
  documentId: string,
  signal?: AbortSignal,
) {
  const data = await getJson<unknown>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/tables`,
    { signal },
  )
  if (!Array.isArray(data)) return []
  return data.flatMap((item): DocumentTable[] => {
    const row = asRecord(item)
    const id = asString(row?.id)
    if (!row || !id) return []
    const cells = Array.isArray(row.cells)
      ? row.cells.flatMap((cell): DocumentTableCell[] => {
          const record = asRecord(cell)
          if (!record) return []
          return [
            {
              row: asNumber(record.row_idx),
              column: asNumber(record.col_idx),
              rowSpan: Math.max(1, asNumber(record.row_span) || 1),
              colSpan: Math.max(1, asNumber(record.col_span) || 1),
              text: asString(record.text),
              header: record.is_header === true,
            },
          ]
        })
      : []
    return [
      {
        id,
        pageNo: asNumber(row.page_no),
        rows: asNumber(row.rows_count),
        columns: asNumber(row.cols_count),
        continued: row.is_multi_page === true || Boolean(row.continued_from),
        cells,
      },
    ]
  })
}

export async function listClauses(documentId: string, signal?: AbortSignal) {
  const data = await getJson<unknown>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/clauses`,
    { signal },
  )
  if (!Array.isArray(data)) {
    throw new Error('Backend không trả cây điều khoản.')
  }
  return data.map(asClause).filter((node): node is ClauseNode => node !== null)
}

export function structureErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return null
  }
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    if (error.status === 403)
      return 'Bạn không có quyền xem cấu trúc hồ sơ này.'
    if (error.status === 404) return 'Không tìm thấy hồ sơ hoặc cây điều khoản.'
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được backend.'
  }
  if (error instanceof Error && error.message) return error.message
  return 'Không tải được cấu trúc hợp đồng. Thử lại.'
}
