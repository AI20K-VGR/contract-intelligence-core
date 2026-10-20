export const SESSION_EXPIRED_EVENT = 'auth:session-expired'

export const SESSION_EXPIRED_MESSAGE =
  'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'

export function notifySessionExpired() {
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
}
