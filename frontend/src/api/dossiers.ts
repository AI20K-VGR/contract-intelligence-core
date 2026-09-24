import { ApiError, postMultipart, requestJson } from './client'

/** OpenAPI `1.1.0+sprint4-ai-integration` — POST /api/v1/dossiers */
export type CreateDossierMetadata = {
  name: string
  tags?: string[]
  notes?: string
}

export type DossierCreated = {
  dossier_id: string
  job_id?: string | null
}

export type CreateDossierInput = {
  contract: File
  metadata: CreateDossierMetadata
  annexes?: File[]
}

/** OpenAPI DossierUpdateBody — PATCH /api/v1/dossiers/{dossier_id} */
export type DossierUpdateBody = {
  name?: string | null
  metadata?: Record<string, unknown> | null
}

const DOSSIERS_PATH = '/api/v1/dossiers'
const PAGE_LIMIT = 100

export type DossierSummary = {
  id: string
  name: string
  batch_id: string | null
  has_conflicts: boolean
  latest_job_status: string | null
  open_review_items: number
  pending_conflicts: number
  metadata: Record<string, unknown> | null
  created_at: string
  document_count: number | null
}

export type DossierListQuery = {
  q?: string
  limit?: number
  offset?: number
  signal?: AbortSignal
}

export type OcrState = 'done' | 'pending' | 'running' | 'error'

export type OcrInspection = {
  state: OcrState
  detail: string | null
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

function asOptionalCount(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (Array.isArray(value)) return value.length
  return null
}

export function normalizeDossierSummary(value: unknown): DossierSummary | null {
  const row = asRecord(value)
  if (!row) return null
  const id = asString(row.id)
  if (!id) return null
  return {
    id,
    name: asString(row.name) || 'Hồ sơ chưa đặt tên',
    batch_id: typeof row.batch_id === 'string' ? row.batch_id : null,
    has_conflicts: row.has_conflicts === true,
    latest_job_status:
      typeof row.latest_job_status === 'string' ? row.latest_job_status : null,
    open_review_items: asNumber(row.open_review_items),
    pending_conflicts: asNumber(row.pending_conflicts),
    metadata: asRecord(row.metadata),
    created_at: asString(row.created_at),
    document_count:
      asOptionalCount(row.document_count) ?? asOptionalCount(row.documents),
  }
}

function dossierRows(data: unknown) {
  if (Array.isArray(data)) return data
  const record = asRecord(data)
  if (!record) return []
  if (Array.isArray(record.items)) return record.items
  if (Array.isArray(record.dossiers)) return record.dossiers
  return []
}

export async function listDossiers(query: DossierListQuery = {}) {
  const params = new URLSearchParams()
  if (query.q) params.set('q', query.q)
  params.set('limit', String(query.limit ?? PAGE_LIMIT))
  params.set('offset', String(query.offset ?? 0))
  const { data, meta } = await requestJson<unknown>(
    `${DOSSIERS_PATH}?${params.toString()}`,
    { signal: query.signal },
  )
  const items = dossierRows(data)
    .map(normalizeDossierSummary)
    .filter((item): item is DossierSummary => item !== null)
  return {
    items,
    total: typeof meta?.total === 'number' ? meta.total : items.length,
  }
}

export async function deleteDossier(id: string) {
  await requestJson<{ id: string; status: string }>(
    `${DOSSIERS_PATH}/${encodeURIComponent(id)}`,
    { method: 'DELETE' },
  )
}

export async function createDossier(input: CreateDossierInput) {
  const form = new FormData()
  form.append('contract', input.contract)
  form.append('metadata', JSON.stringify(input.metadata))
  for (const annex of input.annexes ?? []) {
    form.append('annexes', annex)
  }

  const { data } = await postMultipart<DossierCreated>(DOSSIERS_PATH, form)
  return data
}

export async function patchDossier(dossierId: string, body: DossierUpdateBody) {
  const { data } = await requestJson<unknown>(
    `${DOSSIERS_PATH}/${encodeURIComponent(dossierId)}`,
    { method: 'PATCH', json: body },
  )
  return data
}

export type DossierAccessScope = 'mine' | 'shared_out' | 'shared_in'

export type DossierShareGrant = {
  id: string
  email: string
  display_name: string
}

export async function updateDossierAccess(
  dossierId: string,
  scope: DossierAccessScope,
  sharedWith: DossierShareGrant[],
) {
  const { data } = await requestJson<{
    dossier_id: string
    scope: DossierAccessScope
    shared_with: DossierShareGrant[]
  }>(`${DOSSIERS_PATH}/${encodeURIComponent(dossierId)}/access`, {
    method: 'PUT',
    json: { scope, shared_with: sharedWith },
  })
  return data
}

export function createDossierErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return null
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    }
    if (error.status === 403) {
      return 'Chỉ vận hành và quản trị mới tải hồ sơ được.'
    }
    if (error.status === 404 && error.message === 'Not Found') {
      return 'API tạo hồ sơ chưa có trên backend.'
    }
    if (error.status === 404) {
      return 'Không tìm thấy hồ sơ này.'
    }
    if (error.status === 409) {
      return 'Hồ sơ đang xung đột. Thử lại sau.'
    }
    if (error.status === 422) {
      return (
        error.message || 'Metadata không đúng JSON { name, tags?, notes? }.'
      )
    }
    if (error.status === 400) {
      return error.message || 'Thiếu tệp PDF hợp đồng.'
    }
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được backend. API tạo hồ sơ chưa sẵn sàng.'
  }
  return 'Không tải được hồ sơ. Thử lại.'
}

export function listDossiersErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return null
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    }
    if (error.status === 403) {
      return 'Bạn không có quyền xem danh sách hồ sơ.'
    }
    if (
      error.status === 404 &&
      error.message.trim().toLowerCase() === 'not found'
    ) {
      return 'API danh sách hồ sơ chưa có trên backend.'
    }
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được backend. API danh sách hồ sơ chưa sẵn sàng.'
  }
  if (error instanceof Error && error.message) return error.message
  return 'Không tải được danh sách hồ sơ. Thử lại.'
}

function qualityOf(value: unknown) {
  if (typeof value === 'string') {
    try {
      return asRecord(JSON.parse(value) as unknown)
    } catch {
      return null
    }
  }
  return asRecord(value)
}

function shortOcrError(error: string) {
  const marker = 'RuntimeError:'
  const index = error.lastIndexOf(marker)
  const text = index >= 0 ? error.slice(index + marker.length) : error
  return text.replace(/^SKIPPED:\s*/i, '').trim()
}

export type OcrPageRow = {
  pageNo: number
  kind: string
  status: string
  error: string | null
}

function readOcrPages(data: unknown): OcrPageRow[] {
  return (Array.isArray(data) ? data : []).map((item) => {
    const row = asRecord(item)
    const quality = qualityOf(row?.quality) ?? qualityOf(row?.features)
    const error = asString(quality?.error)
    return {
      pageNo: asNumber(row?.page_no),
      kind: asString(row?.kind),
      status: asString(quality?.ai1_page_status).toUpperCase(),
      error: error ? shortOcrError(error) : null,
    }
  })
}

export async function loadContractOcrPages(
  dossierId: string,
  signal?: AbortSignal,
) {
  const { data: documents } = await requestJson<unknown>(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/documents`,
    { signal },
  )
  const rows = Array.isArray(documents) ? documents : []
  const contract =
    rows.find(
      (item) => asString(asRecord(item)?.role).toLowerCase() === 'contract',
    ) ?? rows[0]
  const record = asRecord(contract)
  const documentId = asString(record?.id)
  if (!documentId) {
    return { documentId: null, filename: null, pages: [] as OcrPageRow[] }
  }
  const { data: pages } = await requestJson<unknown>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/pages`,
    { signal },
  )
  return {
    documentId,
    filename: asString(record?.filename) || null,
    pages: readOcrPages(pages),
  }
}

function inspectionFromPages(
  jobStatus: string | null,
  pages: OcrPageRow[],
): OcrInspection {
  if (pages.length === 0) {
    if (jobStatus === 'processing') return { state: 'running', detail: null }
    if (jobStatus === 'failed') return { state: 'error', detail: null }
    return { state: 'pending', detail: null }
  }
  const failed = pages.find((page) => page.status === 'FAILED' || page.error)
  if (failed) {
    return { state: 'error', detail: failed.error }
  }
  if (jobStatus === 'processing' || jobStatus === 'uploaded') {
    return { state: 'running', detail: null }
  }
  return { state: 'done', detail: null }
}

export async function inspectDossierOcr(
  dossierId: string,
  jobStatus: string | null,
  signal?: AbortSignal,
): Promise<OcrInspection> {
  const loaded = await loadContractOcrPages(dossierId, signal)
  return inspectionFromPages(jobStatus, loaded.pages)
}

export async function restartDossierOcr(dossierId: string) {
  await requestJson(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/ocr`,
    { method: 'POST', json: {} },
  )
}

export function restartOcrErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    if (error.status === 403) return 'Bạn không có quyền chạy lại OCR.'
    if (error.status === 404) return 'Hồ sơ không có tài liệu để OCR.'
    return error.message
  }
  if (error instanceof TypeError) return 'Không kết nối được backend.'
  if (error instanceof Error && error.message) return error.message
  return 'Không chạy lại được OCR. Thử lại.'
}
