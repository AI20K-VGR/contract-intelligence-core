import { InMemoryWebStorage } from 'oidc-client-ts'

/** Khoá oidc-client-ts dùng cho phiên đăng nhập (`oidc.user:<authority>:<client>`). */
export const OIDC_USER_PREFIX = 'oidc.user:'

/** Bỏ `refresh_token` khỏi phiên trước khi lưu; giá trị không phải JSON giữ nguyên. */
export function withoutRefreshToken(value: string): string {
  try {
    const parsed: unknown = JSON.parse(value)
    if (parsed && typeof parsed === 'object' && 'refresh_token' in parsed) {
      const rest = { ...(parsed as Record<string, unknown>) }
      delete rest.refresh_token
      return JSON.stringify(rest)
    }
  } catch {
    // Không phải JSON của phiên: lưu như cũ.
  }
  return value
}

/**
 * Phiên OIDC chỉ nằm trong bộ nhớ của tab, không xuống đĩa (#130). Phiên được
 * lưu không có refresh token, nên mọi lần gia hạn đi bằng iframe `prompt=none`
 * theo cookie phiên SSO HttpOnly của Keycloak, và các tab không tranh nhau một
 * refresh token chỉ dùng được một lần (refresh token rotation).
 *
 * Đây là lớp phòng thủ, không phải "JS không còn refresh token": object `User`
 * mà oidc-client-ts trả cho `signinSilent()`/`signinCallback()` (và sự kiện
 * `userLoaded`) vẫn mang `refresh_token` của token response tới khi bị thu
 * gom. Cách triệt để là Keycloak không cấp refresh token cho client frontend
 * (`use.refresh.tokens=false`, phía Backend).
 */
export class MemoryTokenStorage extends InMemoryWebStorage {
  setItem(key: string, value: string): void {
    super.setItem(key, withoutRefreshToken(value))
  }
}

/** Xoá phiên OIDC bản cũ còn sót trong `localStorage`/`sessionStorage`. */
export function purgeStoredOidcUsers(stores: (Storage | null | undefined)[]) {
  for (const store of stores) {
    if (!store) continue
    try {
      const keys: string[] = []
      for (let index = 0; index < store.length; index += 1) {
        const key = store.key(index)
        if (key?.startsWith(OIDC_USER_PREFIX)) keys.push(key)
      }
      for (const key of keys) store.removeItem(key)
    } catch {
      // Trình duyệt chặn storage: không có gì để dọn.
    }
  }
}
