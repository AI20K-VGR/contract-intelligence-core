// Đổi lỗi bắt được thành câu người dùng hiểu. Lỗi mạng của trình duyệt
// ("Failed to fetch"...) và thông báo tiếng Anh không hiện nguyên văn.

export const NETWORK_MESSAGE =
  'Không kết nối được máy chủ. Vui lòng kiểm tra mạng rồi thử lại.'

/** Đăng nhập gọi thẳng máy chủ đăng nhập (Keycloak), không qua backend. */
export const LOGIN_NETWORK_MESSAGE =
  'Không kết nối được máy chủ đăng nhập. Vui lòng thử lại sau ít phút hoặc báo quản trị viên.'

// Chrome: "Failed to fetch"; Firefox: "NetworkError when attempting to fetch resource.";
// Safari: "Load failed".
const NETWORK_ERROR =
  /failed to fetch|networkerror|load failed|network request failed/i

// Có dấu tiếng Việt thì coi là câu đã viết cho người dùng (BE, kiểm tra ở FE).
const VIETNAMESE = /[À-ỹ]/

export function isNetworkError(cause: unknown) {
  return cause instanceof Error && NETWORK_ERROR.test(cause.message)
}

export function userErrorMessage(
  cause: unknown,
  fallback: string,
  networkMessage = NETWORK_MESSAGE,
) {
  if (isNetworkError(cause)) return networkMessage
  const text = cause instanceof Error ? cause.message.trim() : ''
  if (text && VIETNAMESE.test(text)) return text
  // Câu gốc tiếng Anh/kỹ thuật chỉ ghi Console để tra nguyên nhân.
  if (text) console.warn('[Lỗi kỹ thuật]', text)
  return fallback
}
