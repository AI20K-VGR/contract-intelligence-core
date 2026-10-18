import { analysisRetryKind, jobErrorInfo } from '../api/jobErrors'
import type { AnalysisState } from '../api/structure'
import { MaterialIcon } from './icons'

/**
 * Báo phần phân tích (AI2) chưa xong, bị lỗi, hoặc vừa xong, trên các màn dùng
 * kết quả AI2. Cấu trúc cây có từ lúc OCR xong nên vẫn xem được trong lúc này.
 */
export function AnalysisNotice({
  state,
  errorCode,
  waitingFor,
  percent = null,
  nudge = null,
  justFinished = false,
  onDismiss,
  onRetry,
  retrying = false,
  stalled = false,
  onRecheck,
  showingPrevious = false,
  className = '',
}: {
  state: AnalysisState | null
  errorCode?: string | null
  /** Phần đang chờ AI2, ví dụ "Xung đột và hỏi đáp". */
  waitingFor: string
  /** % AI2 đã xong; null thì chỉ báo đang phân tích. */
  percent?: number | null
  /**
   * Người dùng vừa bấm vào phần bị khoá: banner nháy lên và nói rõ phần đó.
   * `at` đổi mỗi lần bấm để nháy lại.
   */
  nudge?: { label: string; at: number } | null
  /** AI2 vừa xong khi người dùng đang ở trang: báo đã mở khoá. */
  justFinished?: boolean
  onDismiss?: () => void
  /**
   * Có quyền chạy lại: banner lỗi hoặc đã huỷ hiện một nút "Chạy lại". Trang tự
   * chọn cách theo `analysisRetryKind`; hồ sơ sai cấu trúc (DOSSIER_*) không có
   * nút, vì chạy lại vẫn lỗi như cũ.
   */
  onRetry?: () => void
  retrying?: boolean
  /** Quá 10 phút mà AI2 chưa xong (useAnalysisWatch chỉ còn hỏi thưa). */
  stalled?: boolean
  /** Nút "Kiểm tra lại" khi `stalled`: hỏi lại ngay và theo dõi thêm 10 phút. */
  onRecheck?: () => void
  /**
   * AI2 lỗi nhưng hồ sơ còn kết quả của lần phân tích trước: đồ thị và hỏi đáp
   * vẫn mở theo kết quả đó; xung đột thì không (backend chỉ trả của run hiện tại).
   */
  showingPrevious?: boolean
  className?: string
}) {
  if (state === 'done') {
    if (!justFinished) return null
    return (
      <div
        className={`${className} flex flex-wrap items-center gap-x-space-sm gap-y-1 rounded-lg bg-emerald-50 px-space-md py-space-sm font-body-sm text-body-sm text-emerald-900`}
        role="status"
      >
        <MaterialIcon name="check_circle" className="text-[18px]" />
        <span className="min-w-0 flex-1">
          Đã phân tích xong. {waitingFor} đã mở.
        </span>
        {onDismiss ? (
          <button
            aria-label="Đóng thông báo"
            className="shrink-0 rounded-full p-0.5 hover:bg-emerald-100"
            type="button"
            onClick={onDismiss}
          >
            <MaterialIcon name="close" className="text-[16px]" />
          </button>
        ) : null}
      </div>
    )
  }
  if (state !== 'running' && state !== 'failed' && state !== 'cancelled') {
    return null
  }
  if (state === 'running' && stalled) {
    // Job vẫn ở 'extracted' sau 10 phút: /ai2/retry chỉ nhận job đã
    // 'failed', nên không có nút "Chạy lại" ở đây.
    return (
      <div
        className={`${className} flex flex-wrap items-center gap-x-space-sm gap-y-1 rounded-lg bg-amber-50 px-space-md py-space-sm font-body-sm text-body-sm text-amber-950`}
        role="alert"
      >
        <MaterialIcon name="schedule" className="text-[18px]" />
        <span className="min-w-0 flex-1">
          Phân tích lâu hơn bình thường (quá 10 phút). {waitingFor} sẽ tự mở khi
          phân tích xong. Bấm Kiểm tra lại để xem ngay, hoặc báo quản trị viên
          nếu vẫn chưa xong.
        </span>
        {onRecheck ? (
          <button
            className="shrink-0 font-semibold text-primary hover:underline"
            type="button"
            onClick={onRecheck}
          >
            Kiểm tra lại
          </button>
        ) : null}
      </div>
    )
  }
  const running = state === 'running'
  const cancelled = state === 'cancelled'
  const failure = running ? null : jobErrorInfo(errorCode)
  // Câu đầu của banner khi dừng: huỷ hay lỗi.
  const stoppedHead = cancelled
    ? 'Đã huỷ lần phân tích.'
    : showingPrevious
      ? `Lần phân tích mới bị lỗi. ${failure?.message ?? ''}`
      : (failure?.message ?? '')
  const canRetry =
    !running && onRetry && analysisRetryKind(state, errorCode) !== 'none'
  return (
    <div
      key={nudge?.at ?? 'notice'}
      className={`${className} flex flex-wrap items-center gap-x-space-sm gap-y-1 rounded-lg px-space-md py-space-sm font-body-sm text-body-sm ${
        running
          ? 'bg-brand-50 text-on-surface'
          : cancelled
            ? 'bg-surface-container-high text-on-surface'
            : 'bg-error-container text-on-error-container'
      } ${nudge ? 'animate-[pulse_0.6s_ease-in-out_2] ring-2 ring-primary/40' : ''}`}
      role={running ? 'status' : 'alert'}
    >
      <MaterialIcon
        name={running ? 'progress_activity' : cancelled ? 'block' : 'error'}
        className={`text-[18px] ${running ? 'animate-spin text-primary' : ''}`}
      />
      <span className="min-w-0 flex-1">
        {running
          ? `Hệ thống đang phân tích hồ sơ${percent !== null ? ` (${percent}%)` : ''}. ${
              nudge ? nudge.label : waitingFor
            } sẽ mở khi phân tích xong.`
          : showingPrevious
            ? `${stoppedHead} Đồ thị và hỏi đáp đang dùng kết quả của lần phân tích trước; xung đột cần phân tích lại mới xem được.`
            : `${stoppedHead} ${nudge ? nudge.label : waitingFor} chưa có.`}
      </span>
      {running && percent !== null ? (
        <span
          aria-hidden
          className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-brand-100"
        >
          <span
            className="block h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${percent}%` }}
          />
        </span>
      ) : null}
      {canRetry ? (
        <button
          className="shrink-0 font-semibold text-primary hover:underline disabled:opacity-60"
          disabled={retrying}
          type="button"
          onClick={onRetry}
        >
          {retrying ? 'Đang gửi…' : 'Chạy lại'}
        </button>
      ) : null}
    </div>
  )
}
