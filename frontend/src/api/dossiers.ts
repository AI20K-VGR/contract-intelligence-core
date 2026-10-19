import {
  ApiError,
  postMultipartWithProgress,
  requestJson,
  UploadStalledError,
  type UploadOptions,
} from './client'
import {
  isNetworkError,
  NETWORK_MESSAGE,
  userErrorMessage,
} from './errorMessage'

/** OpenAPI `1.1.0+sprint4-ai-integration` — POST /api/v1/dossiers */
export type CreateDossierMetadata = {
  name: string
  /** File trộn hợp đồng + phụ lục: backend chờ POST /split trước khi OCR. */
  split_pending?: boolean
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
  /**
   * v3.3.0: số hợp đồng / phụ lục. `null` khi người gọi không được xem tài liệu
   * (CITATION_READ); `undefined` khi backend cũ không gửi trường này.
   */
  document_counts?: DocumentCounts | null
  /**
   * v3.3.0: tình trạng OCR của hợp đồng đầu tiên. `null` khi hồ sơ chưa có tài
   * liệu hoặc người gọi không được xem trang (QUERY); `undefined` khi backend cũ.
   */
  contract_ocr?: ContractOcrSummary | null
}

export type ContractOcrSummary = {
  document_id: string
  filename: string | null
  /** Số trang đã có kết quả OCR (0 = chưa OCR). */
  page_count: number
  failed_pages: number
  /** Lỗi thô của trang lỗi đầu tiên; null khi trang đó không kèm lỗi. */
  first_error: string | null
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
  /** Nguyên văn lỗi, chỉ hiện cho quản trị viên. */
  technical?: string | null
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

function readDocumentCounts(value: unknown): DocumentCounts | null {
  const record = asRecord(value)
  if (!record) return null
  return {
    contracts: asNumber(record.contracts),
    annexes: asNumber(record.annexes),
  }
}

function readContractOcr(value: unknown): ContractOcrSummary | null {
  const record = asRecord(value)
  if (!record) return null
  return {
    document_id: asString(record.document_id),
    filename: asString(record.filename) || null,
    page_count: asNumber(record.page_count),
    failed_pages: asNumber(record.failed_pages),
    first_error: asString(record.first_error) || null,
  }
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
    // Thiếu khoá (backend trước v3.3.0) khác với giá trị null (không có quyền).
    ...('document_counts' in row
      ? { document_counts: readDocumentCounts(row.document_counts) }
      : {}),
    ...('contract_ocr' in row
      ? { contract_ocr: readContractOcr(row.contract_ocr) }
      : {}),
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

export async function createDossier(
  input: CreateDossierInput,
  options: UploadOptions = {},
) {
  const form = new FormData()
  form.append('contract', input.contract)
  form.append('metadata', JSON.stringify(input.metadata))
  for (const annex of input.annexes ?? []) {
    form.append('annexes', annex)
  }

  const { data } = await postMultipartWithProgress<DossierCreated>(
    DOSSIERS_PATH,
    form,
    options,
  )
  return data
}

export type SplitPartRequest = {
  page_start: number
  page_end: number
  role: 'contract' | 'annex'
}

export type SplitResult = {
  dossier_id: string
  status: string
  documents: {
    id: string
    role: string
    filename: string
    page_start: number
    page_end: number
    page_count: number
  }[]
}

/** POST /api/v1/dossiers/{id}/split — mỗi phần thành một tài liệu rồi mới OCR. */
export async function splitDossier(
  dossierId: string,
  documentId: string,
  parts: SplitPartRequest[],
) {
  const { data } = await requestJson<SplitResult>(
    `${DOSSIERS_PATH}/${encodeURIComponent(dossierId)}/split`,
    { method: 'POST', json: { document_id: documentId, parts } },
  )
  return data
}

export function splitErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === 'DOSSIER_TOO_MANY_DOCUMENTS') return TOO_MANY_DOCUMENTS
    if (error.status === 401) return null
    if (error.status === 403) return 'Bạn chỉ có quyền xem hồ sơ này.'
    if (error.status === 404) return 'Không tìm thấy hồ sơ hoặc file cần tách.'
    if (error.status === 409)
      return 'Hồ sơ này không chờ tách file, hoặc đã bắt đầu xử lý.'
    if (error.status === 422) return `Các phần chưa hợp lệ: ${error.message}`
    return error.message
  }
  if (error instanceof TypeError || isNetworkError(error))
    return NETWORK_MESSAGE
  return 'Không tách được file. Thử lại.'
}

export async function patchDossier(dossierId: string, body: DossierUpdateBody) {
  const { data } = await requestJson<unknown>(
    `${DOSSIERS_PATH}/${encodeURIComponent(dossierId)}`,
    { method: 'PATCH', json: body },
  )
  return data
}

export type DossierAi2Consent = {
  dossier_id: string
  enabled: boolean
  effective_from: 'next_request'
}

export async function updateDossierAi2Consent(
  dossierId: string,
  enabled: boolean,
) {
  const { data } = await requestJson<DossierAi2Consent>(
    `${DOSSIERS_PATH}/${encodeURIComponent(dossierId)}/ai2-content-sharing-consent`,
    { method: 'PATCH', json: { enabled } },
  )
  return data
}

export type DossierAccessScope = 'mine' | 'shared_out' | 'shared_in'

export type DossierShareGrant = {
  id: string
  email: string
  display_name: string
  status?: 'invited' | 'active' | 'disabled'
  /** Bỏ trống ở bản chia sẻ cũ, backend coi là 'edit'. */
  permission?: 'read' | 'edit'
  /** ISO-8601. null hoặc bỏ trống là không hết hạn. */
  expires_at?: string | null
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

export const SHARE_EMAIL_NOT_FOUND =
  'Không tìm thấy email này trong đơn vị của bạn, hoặc người này chưa kích hoạt tài khoản. Vui lòng kiểm tra lại.'

/**
 * Câu báo khi lưu quyền không được. Backend kiểm tra người nhận mới trong
 * Keycloak trước khi lưu (DOC-05b v4.0.0): có người không hợp lệ hay Keycloak
 * không trả lời thì không lưu gì, không gửi thư nào.
 */
export function accessSaveErrorMessage(cause: unknown) {
  if (cause instanceof ApiError) {
    if (cause.code === 'share_recipient_not_found') {
      const rejected = (cause.details as { rejected_emails?: unknown } | null)
        ?.rejected_emails
      const emails = Array.isArray(rejected)
        ? rejected.filter((item): item is string => typeof item === 'string')
        : []
      return emails.length > 0
        ? `${SHARE_EMAIL_NOT_FOUND} (${emails.join(', ')})`
        : SHARE_EMAIL_NOT_FOUND
    }
    if (cause.code === 'keycloak_unavailable') {
      return 'Chưa kiểm tra được người nhận vì dịch vụ đăng nhập không phản hồi. Chưa lưu gì, vui lòng thử lại.'
    }
    if (cause.message) return cause.message
  }
  return 'Chưa lưu được quyền truy cập.'
}

export const MAX_DOSSIER_DOCUMENTS = 6
export const TOO_MANY_DOCUMENTS = `Hồ sơ tối đa ${MAX_DOSSIER_DOCUMENTS} tài liệu`

const UPLOAD_ERROR_MESSAGES: Record<string, string> = {
  UPLOAD_CANCELLED:
    'Lượt tải lên này đã dừng vì có lượt tải lên mới hơn. Vui lòng tải lên lại.',
  UPLOAD_NOT_OPEN: 'Lượt tải lên này đã dừng. Vui lòng tải lên lại.',
  UPLOAD_EXPIRED: 'Lượt tải lên đã quá 24 giờ. Vui lòng tải lên lại.',
  UPLOAD_SIZE_MISMATCH:
    'Tệp máy chủ nhận được không khớp với tệp đã chọn. Vui lòng tải lên lại.',
  UPLOAD_COMPLETING:
    'Máy chủ vẫn đang ghép tệp. Vui lòng xem lại danh sách hồ sơ sau ít phút.',
  UPLOAD_MISSING_CHUNKS:
    'Máy chủ chưa nhận đủ tệp. Vui lòng kiểm tra mạng rồi tải lên lại.',
}

export function createDossierErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return null
  }
  if (error instanceof UploadStalledError) return error.message
  if (error instanceof ApiError) {
    if (error.code === 'DOSSIER_TOO_MANY_DOCUMENTS') return TOO_MANY_DOCUMENTS
    // Tải theo khúc (/uploads, DOC-05b v4.2.0 §3.3): message của backend là
    // tiếng Anh, hiển thị theo mã.
    const uploadMessage = error.code ? UPLOAD_ERROR_MESSAGES[error.code] : null
    if (uploadMessage) return uploadMessage
    if (error.status === 401) {
      return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    }
    if (error.status === 403) {
      return 'Chỉ vận hành và quản trị mới tải hồ sơ được.'
    }
    if (error.status === 404 && error.message === 'Not Found') {
      return 'Chức năng tạo hồ sơ chưa sẵn sàng. Vui lòng báo quản trị viên.'
    }
    if (error.status === 404) {
      return 'Không tìm thấy hồ sơ này.'
    }
    if (error.status === 409) {
      return 'Hồ sơ đang xung đột. Thử lại sau.'
    }
    if (error.status === 422) {
      return userErrorMessage(error, 'Thông tin hồ sơ không hợp lệ.')
    }
    if (error.status === 400) {
      return userErrorMessage(error, 'Thiếu tệp PDF hợp đồng.')
    }
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được máy chủ nên chưa tạo được hồ sơ. Vui lòng thử lại.'
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
      return 'Chức năng xem danh sách hồ sơ chưa sẵn sàng. Vui lòng báo quản trị viên.'
    }
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được máy chủ nên chưa tải được danh sách hồ sơ. Vui lòng thử lại.'
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

const OCR_NOT_READY =
  'Hệ thống chưa sẵn sàng để đọc tài liệu. Vui lòng báo quản trị viên.'
const OCR_SERVICE_DOWN =
  'Dịch vụ đọc tài liệu đang gặp sự cố. Vui lòng thử lại sau.'

// Thứ tự quan trọng: lỗi AI1 lồng nhau ("… unavailable: APIConnectionError: …"),
// nên xét nguyên nhân cụ thể trước, câu chung "unavailable" sau cùng.
// Mã HTTP chỉ tính khi đi kèm ngữ cảnh ("HTTP 401", "status 503",
// "status_code=500"): một số trần có thể là số trang, kích thước hay id dòng.
const HTTP_STATUS = String.raw`(?:HTTP|status(?:_code)?)\s*[:=]?\s*`
const OCR_ERROR_RULES: [RegExp, string][] = [
  // Mất kết nối và quá lâu là nguyên nhân cụ thể nhất: xét trước, kể cả khi
  // câu lỗi có số giống mã HTTP ("page 401: ReadTimeout").
  [
    /APIConnectionError|ConnectionError|Connection error|ConnectError/i,
    'Mất kết nối khi đọc tài liệu. Vui lòng bấm "Đọc lại".',
  ],
  [/Timeout|timed? ?out/i, 'Đọc tài liệu quá lâu. Vui lòng bấm "Đọc lại".'],
  [
    new RegExp(
      `_API_KEY is not set|disabled in configuration|AuthenticationError|PermissionDeniedError|${HTTP_STATUS}40[13]\\b`,
      'i',
    ),
    OCR_NOT_READY,
  ],
  [
    /RateLimitError|rate limit|\b429\b/i,
    'Hệ thống đang quá tải. Vui lòng thử lại sau ít phút.',
  ],
  [
    new RegExp(
      `InternalServerError|ServiceUnavailable|${HTTP_STATUS}50[023]\\b`,
      'i',
    ),
    OCR_SERVICE_DOWN,
  ],
  [
    /not a valid PDF/i,
    'Tệp không phải PDF hợp lệ. Vui lòng kiểm tra và tải lại tệp.',
  ],
  [
    /empty or exceeds the 50 MB/i,
    'Tệp rỗng hoặc lớn hơn 50 MB. Vui lòng tải tệp khác.',
  ],
  [
    /source_sha256 does not match|cannot download source/i,
    'Không lấy được tệp để đọc. Vui lòng bấm "Đọc lại".',
  ],
  [/document has no pages/i, 'Tệp không có trang nào để đọc.'],
  [/unavailable/i, OCR_SERVICE_DOWN],
]

/** Lỗi AI1 là tiếng Anh, kỹ thuật; đổi sang câu người dùng hiểu và làm theo được. */
export function ocrErrorMessage(error: string) {
  const rule = OCR_ERROR_RULES.find(([pattern]) => pattern.test(error))
  return rule
    ? rule[1]
    : 'Không đọc được tài liệu. Vui lòng bấm "Đọc lại"; nếu vẫn lỗi, báo quản trị viên.'
}

/** Nguyên văn lỗi AI1 (bỏ tiền tố SKIPPED) để quản trị viên tra nguyên nhân. */
export function ocrErrorDetail(error: string) {
  return error.replace(/^SKIPPED:\s*/i, '').trim()
}

export type OcrPageRow = {
  pageNo: number
  kind: string
  status: string
  error: string | null
  errorDetail: string | null
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
      error: error ? ocrErrorMessage(error) : null,
      errorDetail: error ? ocrErrorDetail(error) : null,
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
  return {
    documentId,
    filename: asString(record?.filename) || null,
    pages: await loadDocumentOcrPages(documentId, signal),
  }
}

export async function loadDocumentOcrPages(
  documentId: string,
  signal?: AbortSignal,
) {
  const { data: pages } = await requestJson<unknown>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/pages`,
    { signal },
  )
  return readOcrPages(pages)
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
    return {
      state: 'error',
      detail: failed.error,
      technical: failed.errorDetail,
    }
  }
  if (jobStatus === 'processing' || jobStatus === 'uploaded') {
    return { state: 'running', detail: null }
  }
  return { state: 'done', detail: null }
}

/**
 * Cùng cách đọc như `inspectionFromPages`, nhưng từ `contract_ocr` của danh
 * sách (v3.3.0), không phải gọi `/documents` và `/pages` cho từng hồ sơ.
 * `null` (chưa có tài liệu, hoặc không được xem trang) thì chỉ theo trạng thái job.
 */
export function inspectionFromContractOcr(
  jobStatus: string | null,
  ocr: ContractOcrSummary | null,
): OcrInspection {
  if (!ocr || ocr.page_count === 0) return inspectionFromPages(jobStatus, [])
  if (ocr.failed_pages > 0) {
    return {
      state: 'error',
      detail: ocr.first_error ? ocrErrorMessage(ocr.first_error) : null,
      technical: ocr.first_error ? ocrErrorDetail(ocr.first_error) : null,
    }
  }
  if (jobStatus === 'processing' || jobStatus === 'uploaded') {
    return { state: 'running', detail: null }
  }
  return { state: 'done', detail: null }
}

/**
 * Số tài liệu và tình trạng OCR mà danh sách đã trả sẵn, theo mã hồ sơ. Hồ sơ
 * nào backend không gửi trường (bản trước v3.3.0) thì không có mặt ở đây, và
 * trang gọi `loadDocumentCounts` / `inspectDossierOcr` như cũ cho hồ sơ đó.
 * `null` nghĩa là không có quyền: không gọi bù, vì gọi cũng nhận 403.
 */
export function listedDossierFacts(summaries: DossierSummary[]) {
  const counts: Record<string, DocumentCounts | null> = {}
  const ocr: Record<string, OcrInspection> = {}
  for (const summary of summaries) {
    if (summary.document_counts !== undefined) {
      counts[summary.id] = summary.document_counts
    }
    if (summary.contract_ocr !== undefined) {
      ocr[summary.id] = inspectionFromContractOcr(
        summary.latest_job_status,
        summary.contract_ocr,
      )
    }
  }
  return { counts, ocr }
}

/** Gọi `/documents` và `/pages` cho một hồ sơ: chỉ dùng khi backend cũ không trả `contract_ocr`. */
export async function inspectDossierOcr(
  dossierId: string,
  jobStatus: string | null,
  signal?: AbortSignal,
): Promise<OcrInspection> {
  const loaded = await loadContractOcrPages(dossierId, signal)
  return inspectionFromPages(jobStatus, loaded.pages)
}

export type DocumentCounts = { contracts: number; annexes: number }

/**
 * Đếm tài liệu của hồ sơ theo vai trò bằng `/documents`. Từ v3.3.0 danh sách đã
 * trả `document_counts`; hàm này chỉ dùng khi backend cũ không gửi trường đó.
 */
export async function loadDocumentCounts(
  dossierId: string,
  signal?: AbortSignal,
): Promise<DocumentCounts> {
  const { data } = await requestJson<unknown>(
    `${DOSSIERS_PATH}/${encodeURIComponent(dossierId)}/documents`,
    { signal },
  )
  const counts: DocumentCounts = { contracts: 0, annexes: 0 }
  for (const item of Array.isArray(data) ? data : []) {
    const role = asString(asRecord(item)?.role).toLowerCase()
    if (role === 'contract') counts.contracts += 1
    else if (role === 'annex') counts.annexes += 1
  }
  return counts
}

/** "1 hợp đồng · 3 phụ lục"; bỏ phần bằng 0. Rỗng khi hồ sơ chưa có tài liệu. */
export function formatDocumentCounts(counts: DocumentCounts): string {
  const parts: string[] = []
  if (counts.contracts > 0) parts.push(`${counts.contracts} hợp đồng`)
  if (counts.annexes > 0) parts.push(`${counts.annexes} phụ lục`)
  return parts.join(' · ')
}

export async function restartDossierOcr(dossierId: string) {
  await requestJson(`/api/v1/dossiers/${encodeURIComponent(dossierId)}/ocr`, {
    method: 'POST',
    json: {},
  })
}

/** Chạy lại đúng bước lỗi: OCR giữ kết quả đã xong, AI2 không OCR lại. */
export async function retryDossierFailed(
  dossierId: string,
  kind: 'ai2' | 'ocr',
) {
  const path = kind === 'ai2' ? 'ai2/retry' : 'ocr/retry-failed'
  await requestJson(
    `/api/v1/dossiers/${encodeURIComponent(dossierId)}/${path}`,
    { method: 'POST', json: {} },
  )
}

/**
 * "Chạy lại OCR" mà không trả tiền lại cho trang đã đọc: thử chạy lại phần lỗi
 * trước (giữ kết quả OCR đã có, kể cả kết quả về sau khi run bị lỗi). Chỉ chạy
 * lại toàn bộ khi backend báo không có phần lỗi để chạy lại (409).
 */
export async function rerunDossierOcr(dossierId: string) {
  try {
    await retryDossierFailed(dossierId, 'ocr')
    return 'retry-failed' as const
  } catch (cause) {
    if (!(cause instanceof ApiError) || cause.status !== 409) throw cause
  }
  await restartDossierOcr(dossierId)
  return 'restart' as const
}

export function restartOcrErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    if (error.status === 403) return 'Bạn không có quyền đọc lại tài liệu.'
    if (error.status === 404) return 'Hồ sơ không có tài liệu để đọc.'
    return error.message
  }
  if (error instanceof TypeError || isNetworkError(error))
    return NETWORK_MESSAGE
  if (error instanceof Error && error.message) return error.message
  return 'Không đọc lại được tài liệu. Thử lại.'
}
