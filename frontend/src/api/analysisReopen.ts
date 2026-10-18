import type { DossierStructure } from './structure'

// /ai2/retry trả 202 rồi worker mới mở lại job sang 'extracted'. Trang hỏi lại
// dày lúc đầu (15 lần × 2 giây), sau đó 10 giây một lần, tối đa 5 phút.
export const REOPEN_FAST_MS = 2000
export const REOPEN_FAST_TRIES = 15
export const REOPEN_SLOW_MS = 10_000
export const REOPEN_LIMIT_MS = 5 * 60_000

export type ReopenResult =
  | { kind: 'reopened'; next: DossierStructure }
  /** Hết 5 phút mà job vẫn 'failed': chưa nhận, hoặc AI2 đã lỗi lại. */
  | { kind: 'timeout' }
  /** Đã có vòng chờ mới, đổi hồ sơ hoặc rời trang. */
  | { kind: 'abandoned' }

export type ReopenDeps = {
  getDossierStructure: (dossierId: string) => Promise<DossierStructure>
  /** false khi vòng này không còn là vòng đang chờ: dừng ngay. */
  isCurrent: () => boolean
  /** Hết phần hỏi dày mà chưa thấy job mở lại. */
  onSlow?: () => void
}

/**
 * Chờ job rời 'failed' sau "Chạy lại". FE không biết job đã chạy lại rồi lỗi
 * tiếp hay chưa (không có updated_at), nên chờ có giới hạn thay vì chờ mãi.
 */
export async function waitForAnalysisReopen(
  dossierId: string,
  deps: ReopenDeps,
): Promise<ReopenResult> {
  let waited = 0
  for (let n = 0; waited < REOPEN_LIMIT_MS; n += 1) {
    if (n === REOPEN_FAST_TRIES) deps.onSlow?.()
    const delay = n < REOPEN_FAST_TRIES ? REOPEN_FAST_MS : REOPEN_SLOW_MS
    await new Promise((resolve) => setTimeout(resolve, delay))
    waited += delay
    if (!deps.isCurrent()) return { kind: 'abandoned' }
    let next: DossierStructure
    try {
      next = await deps.getDossierStructure(dossierId)
    } catch {
      // Lỗi mạng tạm thời: lần hỏi sau thử lại.
      continue
    }
    if (!deps.isCurrent()) return { kind: 'abandoned' }
    if (next.latestJobStatus !== 'failed') return { kind: 'reopened', next }
  }
  return { kind: 'timeout' }
}
