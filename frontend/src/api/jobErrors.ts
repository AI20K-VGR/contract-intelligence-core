// Mã lỗi backend gắn vào run/job (xem events_router.py và contract_router.py).
// Lỗi tạm thì chạy lại được; lỗi vĩnh viễn thì chỉ báo.
export type JobRetryKind = 'ai2' | 'ocr' | 'none'

export type JobErrorInfo = {
  code: string | null
  message: string
  retry: JobRetryKind
}

// Khớp _AI2_RETRYABLE_ERRORS ở backend: các mã này đi qua /ai2/retry.
const AI2_RETRYABLE = new Set(['AI2_PROCESSING_FAILED', 'AI2_TIMEOUT'])

const PERMANENT: Record<string, string> = {
  DOSSIER_DELETED: 'Hồ sơ đã bị xóa.',
  dossier_deleted: 'Hồ sơ đã bị xóa.',
  DOSSIER_TOO_MANY_DOCUMENTS: 'Hồ sơ tối đa 6 tài liệu.',
}

const MESSAGES: Record<string, string> = {
  AI2_TIMEOUT: 'AI2 xử lý quá thời gian. Có thể chạy lại.',
  PROCESSING_TIMEOUT: 'AI2 xử lý quá thời gian. Có thể chạy lại.',
  AI2_PROCESSING_FAILED: 'AI2 xử lý lỗi tạm thời. Có thể chạy lại.',
  AI2_UNAVAILABLE: 'Dịch vụ AI2 chưa sẵn sàng. Thử lại sau.',
  DISPATCH_FAILED: 'Không gửi được hồ sơ đi xử lý. Thử lại.',
}

export function jobErrorInfo(code: string | null | undefined): JobErrorInfo {
  const normalized = code?.trim() || null
  if (!normalized) {
    return { code: null, message: 'Hồ sơ xử lý lỗi.', retry: 'ocr' }
  }
  const permanent = PERMANENT[normalized]
  if (permanent) return { code: normalized, message: permanent, retry: 'none' }
  return {
    code: normalized,
    message: MESSAGES[normalized] ?? 'Hồ sơ xử lý lỗi.',
    retry: AI2_RETRYABLE.has(normalized) ? 'ai2' : 'ocr',
  }
}
