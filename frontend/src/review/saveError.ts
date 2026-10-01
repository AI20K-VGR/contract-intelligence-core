import { ApiError } from '../api/client'

/*
 * Backend trả 403 vì ba lý do khác nhau, và câu chữ gốc có khi là tiếng Anh.
 * Người dùng cần biết mình phải liên hệ ai, nên đổi thành câu rõ ràng.
 */
export const READ_ONLY_MESSAGE =
  'Bạn chỉ có quyền xem hồ sơ này. Vui lòng liên hệ người chia sẻ để sửa quyền.'

export const ROLE_DENIED_MESSAGE =
  'Vai trò hiện tại của bạn không được thẩm định. Vui lòng liên hệ quản trị viên để đổi vai trò.'

export const EXPIRED_MESSAGE =
  'Quyền chia sẻ hồ sơ này đã hết hạn. Vui lòng liên hệ người chia sẻ để gia hạn.'

export function reviewErrorMessage(cause: unknown, fallback: string) {
  if (cause instanceof ApiError && cause.status === 403) {
    const text = cause.message
    if (/insufficient role/i.test(text) || /vai trò/i.test(text)) {
      return ROLE_DENIED_MESSAGE
    }
    if (/hết hạn/i.test(text) && !/chỉ có quyền xem/i.test(text)) {
      return EXPIRED_MESSAGE
    }
    if (/chỉ có quyền xem/i.test(text)) return READ_ONLY_MESSAGE
    return text || READ_ONLY_MESSAGE
  }
  return cause instanceof Error ? cause.message : fallback
}
