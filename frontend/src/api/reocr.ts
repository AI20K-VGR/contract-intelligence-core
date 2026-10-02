import { ApiError, requestJson } from './client'

export type ReOcrProfile =
  | 'high_res_binarize'
  | 'table_optimized'
  | 'handwritten_vietnamese'

export const REOCR_PROFILES: Array<{ value: ReOcrProfile; label: string }> = [
  { value: 'high_res_binarize', label: 'Ảnh mờ, nhị phân độ phân giải cao' },
  { value: 'table_optimized', label: 'Tối ưu cho bảng' },
  { value: 'handwritten_vietnamese', label: 'Chữ viết tay tiếng Việt' },
]

export type ReOcrRequest = {
  id: string
  documentId: string
  profile: string
  pageNumbers: number[]
  status: string
  reason: string | null
  createdAt: string | null
  completedAt: string | null
}

const FINISHED = new Set(['completed', 'succeeded', 'failed', 'cancelled'])

export function isReOcrFinished(status: string) {
  return FINISHED.has(status.toLowerCase())
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function text(row: Record<string, unknown>, key: string) {
  const value = row[key]
  return typeof value === 'string' && value ? value : null
}

function reocrRequest(value: unknown): ReOcrRequest | null {
  const row = asRecord(value)
  const id = row ? text(row, 'id') : null
  if (!row || !id) return null
  return {
    id,
    documentId: text(row, 'document_id') ?? '',
    profile: text(row, 'profile') ?? '',
    pageNumbers: Array.isArray(row.page_numbers)
      ? row.page_numbers.filter((n): n is number => typeof n === 'number')
      : [],
    status: text(row, 'status') ?? '',
    reason: text(row, 'reason'),
    createdAt: text(row, 'created_at'),
    completedAt: text(row, 'completed_at'),
  }
}

/** POST /documents/{id}/re-ocr: OCR lại các trang chọn bằng profile khác. */
export async function createReOcr(
  documentId: string,
  input: { profile: ReOcrProfile; pageNumbers: number[]; reason?: string },
) {
  const { data } = await requestJson<unknown>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/re-ocr`,
    {
      method: 'POST',
      json: {
        profile: input.profile,
        page_numbers: input.pageNumbers,
        reason: input.reason?.trim() || undefined,
      },
    },
  )
  return reocrRequest(data)
}

/** GET /re-ocr-requests/{id}: poll trạng thái. */
export async function getReOcrRequest(requestId: string, signal?: AbortSignal) {
  const { data } = await requestJson<unknown>(
    `/api/v1/re-ocr-requests/${encodeURIComponent(requestId)}`,
    { signal },
  )
  return reocrRequest(data)
}

export async function listReOcrRequests(
  documentId: string,
  signal?: AbortSignal,
) {
  const { data } = await requestJson<unknown>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/re-ocr-requests`,
    { signal },
  )
  return (Array.isArray(data) ? data : [])
    .map(reocrRequest)
    .filter((item): item is ReOcrRequest => item !== null)
}

export function reOcrErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    if (error.status === 403) return 'Bạn không có quyền OCR lại tài liệu này.'
    if (error.status === 404) return 'Không tìm thấy tài liệu.'
    if (error.status === 400 || error.status === 422) {
      return error.message || 'Yêu cầu OCR lại chưa hợp lệ.'
    }
    return error.message
  }
  if (error instanceof TypeError) return 'Không kết nối được backend.'
  return 'Không gửi được yêu cầu OCR lại. Thử lại.'
}
