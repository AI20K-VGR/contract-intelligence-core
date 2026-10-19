import { ErrorResponse } from 'oidc-client-ts'

// Keycloak trả các mã này khi phiên SSO không còn (hết hạn, bị khoá, đã đăng
// xuất): gia hạn lại cũng vô ích, phải đăng nhập lại.
const SESSION_ENDED = new Set([
  'login_required',
  'interaction_required',
  'consent_required',
  'account_selection_required',
  'invalid_grant',
])

/**
 * Gia hạn bị từ chối vì phiên Keycloak đã hết. Lỗi khác (iframe quá thời gian
 * chờ khi tab chạy nền bị trình duyệt làm chậm, mất mạng) thì phiên có thể vẫn
 * còn: giữ người dùng và thử lại sau, không đăng xuất (#130).
 */
export function isSessionEnded(cause: unknown): boolean {
  return (
    cause instanceof ErrorResponse &&
    cause.error !== null &&
    SESSION_ENDED.has(cause.error)
  )
}
