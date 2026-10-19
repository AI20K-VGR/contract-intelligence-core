// Mỗi lúc chỉ một lần gia hạn phiên trong cả trình duyệt (Web Locks), để nhiều
// tab hết hạn cùng lúc không mở nhiều iframe tới Keycloak một lượt (#130).
export const RENEW_LOCK_NAME = 'lexis-refresh'

type LockManagerLike = {
  request: <T>(name: string, callback: () => Promise<T>) => Promise<T>
}

function browserLocks(): LockManagerLike | null {
  if (typeof navigator === 'undefined') return null
  const locks = (navigator as Navigator & { locks?: LockManagerLike }).locks
  return locks && typeof locks.request === 'function' ? locks : null
}

/** Chạy `task` dưới khoá `lexis-refresh`; không có Web Locks thì chạy thẳng. */
export function withRenewLock<T>(
  task: () => Promise<T>,
  locks: LockManagerLike | null = browserLocks(),
): Promise<T> {
  return locks ? locks.request(RENEW_LOCK_NAME, task) : task()
}
