import { ApiError } from './client'
import {
  isNetworkError,
  NETWORK_MESSAGE,
  userErrorMessage,
} from './errorMessage'

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
  DOSSIER_CONTRACT_REQUIRED:
    'Hồ sơ cần đúng một hợp đồng. Vui lòng tải lại hồ sơ.',
  DOSSIER_CONTRACT_NOT_UNIQUE:
    'Hồ sơ chỉ được có một hợp đồng. Vui lòng tải lại hồ sơ.',
}

// DOSSIER_* khác (worker từ chối hồ sơ sai cấu trúc): chạy lại vẫn lỗi y như cũ.
const DOSSIER_SHAPE_MESSAGE =
  'Hồ sơ không đúng cấu trúc để phân tích. Vui lòng tải lại hồ sơ.'

const MESSAGES: Record<string, string> = {
  AI2_TIMEOUT: 'Phân tích hồ sơ quá lâu. Bạn có thể chạy lại.',
  PROCESSING_TIMEOUT: 'Phân tích hồ sơ quá lâu. Bạn có thể chạy lại.',
  AI2_PROCESSING_FAILED: 'Phân tích hồ sơ bị gián đoạn. Bạn có thể chạy lại.',
  AI2_UNAVAILABLE: 'Hệ thống phân tích chưa sẵn sàng. Vui lòng thử lại sau.',
  RUN_CANCELLED: 'Đã hủy lần xử lý. Bạn có thể chạy tiếp.',
  DISPATCH_FAILED: 'Không gửi được hồ sơ đi xử lý. Thử lại.',
  // DOC-05b v3.2.0: AI1 trả mọi trang lỗi (thường do thiếu cấu hình OCR), nên
  // không có gì gửi sang AI2. Chạy lại OCR sau khi sửa cấu hình.
  AI1_NO_READABLE_PAGE:
    'OCR không đọc được trang nào của tài liệu. Kiểm tra cấu hình OCR rồi chạy lại phần OCR lỗi.',
}

// Mã worker gắn khi AI2 lỗi (xem _fail_ai2_run).
const AI2_FAILURES = new Set([
  ...AI2_RETRYABLE,
  'AI2_UNAVAILABLE',
  'AI2_BLOCKED',
  'PROCESSING_TIMEOUT',
])

export function isCancelledJob(
  status: string | null | undefined,
  code: string | null | undefined,
) {
  return status === 'cancelled' || code?.trim() === 'RUN_CANCELLED'
}

export type StepStatuses = Record<string, { status: string } | undefined>

// Job failed khi OCR đã xong thì lỗi nằm ở AI2. Xác định theo bước đã chạy
// (S8 xong = OCR đủ tài liệu; S4 lỗi = AI2 gãy), vì AI2 trả cả mã tùy ý
// (errors[0].code) và DOSSIER_* nên danh sách mã không bao hết.
export function isAi2Failure(
  code: string | null | undefined,
  steps: StepStatuses = {},
) {
  if (steps.S4?.status === 'failed' || steps.S8?.status === 'succeeded') {
    return true
  }
  const normalized = code?.trim() ?? ''
  return AI2_FAILURES.has(normalized) || normalized.startsWith('DOSSIER_')
}

export function jobErrorInfo(code: string | null | undefined): JobErrorInfo {
  const normalized = code?.trim() || null
  if (!normalized) {
    return {
      code: null,
      message: 'Xử lý hồ sơ không thành công. Vui lòng thử lại.',
      retry: 'ocr',
    }
  }
  const permanent = PERMANENT[normalized]
  if (permanent) return { code: normalized, message: permanent, retry: 'none' }
  if (normalized.startsWith('DOSSIER_')) {
    return { code: normalized, message: DOSSIER_SHAPE_MESSAGE, retry: 'none' }
  }
  return {
    code: normalized,
    message:
      MESSAGES[normalized] ?? 'Xử lý hồ sơ không thành công. Vui lòng thử lại.',
    retry: AI2_RETRYABLE.has(normalized) ? 'ai2' : 'ocr',
  }
}

/**
 * Nút "Chạy lại" duy nhất khi phần phân tích (AI2) lỗi hoặc bị huỷ sau OCR:
 * - 'ai2': lỗi tạm của AI2, gọi /ai2/retry (backend chỉ nhận hai mã này);
 * - 'resume': run bị huỷ sau OCR, gọi /ocr/retry-failed để chạy tiếp, giữ phần
 *   OCR đã đọc;
 * - 'reprocess': lỗi AI2 khác (BLOCKED, mã AI2 tự đặt...), chạy lại toàn bộ
 *   (OCR và AI2 từ đầu), cần người dùng xác nhận;
 * - 'none': hồ sơ sai cấu trúc (DOSSIER_*), chạy lại vẫn lỗi như cũ.
 */
export type AnalysisRetry = 'ai2' | 'resume' | 'reprocess' | 'none'

export function analysisRetryKind(
  state: string | null | undefined,
  code: string | null | undefined,
): AnalysisRetry {
  if (state === 'cancelled') return 'resume'
  if (state !== 'failed') return 'none'
  const normalized = code?.trim() ?? ''
  if (AI2_RETRYABLE.has(normalized)) return 'ai2'
  if (normalized.startsWith('DOSSIER_') || PERMANENT[normalized]) return 'none'
  return 'reprocess'
}

/**
 * Câu báo khi nút "Chạy lại" phân tích không gửi được. 409: người khác (hoặc
 * tab khác) đã chạy lại trước, trang cần tải lại trạng thái.
 */
export function analysisRetryErrorMessage(cause: unknown) {
  if (cause instanceof ApiError) {
    if (cause.status === 403)
      return 'Bạn không có quyền chạy lại phân tích hồ sơ này.'
    if (cause.status === 409)
      return 'Hồ sơ đã được chạy lại hoặc đang chạy. Đang tải lại trạng thái.'
  }
  if (cause instanceof TypeError || isNetworkError(cause))
    return NETWORK_MESSAGE
  return userErrorMessage(
    cause,
    'Không chạy lại được phân tích. Vui lòng thử lại.',
  )
}
