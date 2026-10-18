import { ApiError } from './client'
import {
  ai2ProgressPercent,
  findLatestRunId,
  listRunSteps,
  stepFromEvent,
  watchRun,
  type RunStep,
} from './runEvents'
import { getDossierStructure, type DossierStructure } from './structure'

/**
 * Hồ sơ phân tích xong dưới 10 phút. Quá mốc này mà job vẫn ở 'extracted' thì
 * báo người dùng (có thể kẹt, ví dụ worker dừng giữa chừng), đóng SSE và chỉ
 * hỏi lại thưa, để AI2 xong muộn thì trang vẫn tự mở. Backend tự đánh 'failed'
 * khi AI2 quá hạn, nên đây chỉ là lưới an toàn.
 */
export const ANALYSIS_STALL_MS = 10 * 60 * 1000

/** SSE bị từ chối, hoặc stream đã đóng mà job chưa rời 'extracted': hỏi thưa. */
export const FALLBACK_POLL_MS = 15000

/** Đã quá 10 phút: hỏi thưa hơn nữa, tới khi job rời 'extracted'. */
export const STALLED_POLL_MS = 60000

type WatchStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

export type AnalysisWatchDeps = {
  findLatestRunId: typeof findLatestRunId
  listRunSteps: typeof listRunSteps
  getDossierStructure: typeof getDossierStructure
  watchRun: typeof watchRun
  /** Nơi nhớ lúc bắt đầu theo dõi mỗi run; null thì đếm lại mỗi lần vào trang. */
  storage: WatchStorage | null
  now: () => number
}

export type AnalysisWatchHandlers = {
  /** % AI2 đã xong theo các bước BE ghi; null khi chưa có số liệu. */
  onPercent: (percent: number | null) => void
  /** Đã quá 10 phút mà job vẫn ở 'extracted'. */
  onStalled: () => void
  /** Job rời 'extracted' (AI2 xong, lỗi hoặc bị huỷ): gọi đúng một lần. */
  onDone: (next: DossierStructure) => void
  /** Hồ sơ không còn mở được (403/404: bị xoá hoặc bị thu quyền): đã dừng. */
  onGone?: () => void
}

function sessionStore(): WatchStorage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage
  } catch {
    return null
  }
}

const browserDeps: AnalysisWatchDeps = {
  findLatestRunId,
  listRunSteps,
  getDossierStructure,
  watchRun,
  get storage() {
    return sessionStore()
  },
  now: () => Date.now(),
}

const startedKey = (id: string) => `ai2-watch-started:${id}`

/**
 * Theo dõi phần phân tích (AI2) của một hồ sơ đang ở 'extracted': nghe SSE
 * `step.changed` của run để cập nhật %, và chỉ hỏi lại hồ sơ khi run đổi trạng
 * thái hoặc SSE mất kết nối, không hỏi định kỳ.
 *
 * Mốc 10 phút tính từ lần đầu theo dõi run này trong tab (`sessionStorage`), nên
 * rời trang rồi quay lại vẫn tính tiếp. `restart` (nút "Kiểm tra lại") đặt lại
 * mốc. Trả hàm dừng theo dõi.
 */
export function startAnalysisWatch(
  dossierId: string,
  handlers: AnalysisWatchHandlers,
  { restart = false }: { restart?: boolean } = {},
  deps: AnalysisWatchDeps = browserDeps,
): () => void {
  // controller: cả lần theo dõi (dừng thì huỷ). stream: riêng SSE, đóng khi quá
  // 10 phút; việc hỏi thưa vẫn chạy tiếp.
  const controller = new AbortController()
  const stream = new AbortController()
  const storage = deps.storage
  let finished = false
  let pollTimer: ReturnType<typeof setTimeout> | undefined
  let stallTimer: ReturnType<typeof setTimeout> | undefined
  let pollMs = FALLBACK_POLL_MS
  let runKey: string | null = null
  const steps: Record<string, RunStep> = {}

  function stall() {
    if (finished) return
    pollMs = STALLED_POLL_MS
    stream.abort()
    handlers.onStalled()
    schedulePoll()
  }

  /** `id`: run đang theo dõi, hoặc hồ sơ khi chưa tìm được run. */
  function armStall(id: string) {
    runKey = startedKey(id)
    let started: number | null = null
    try {
      if (restart) storage?.removeItem(runKey)
      const stored = Number(storage?.getItem(runKey))
      if (Number.isFinite(stored) && stored > 0) started = stored
      if (started === null) {
        started = deps.now()
        storage?.setItem(runKey, String(started))
      }
    } catch {
      started ??= deps.now()
    }
    const left = Math.max(0, ANALYSIS_STALL_MS - (deps.now() - started))
    stallTimer = setTimeout(stall, left)
  }

  function stop() {
    finished = true
    clearTimeout(stallTimer)
    clearTimeout(pollTimer)
    stream.abort()
    controller.abort()
  }

  function finish(next: DossierStructure) {
    if (finished) return
    stop()
    try {
      if (runKey) storage?.removeItem(runKey)
    } catch {
      // Không xoá được mốc: lần sau chỉ đếm sai, không ảnh hưởng kết quả.
    }
    handlers.onDone(next)
  }

  /** true khi đã ngừng theo dõi (job rời 'extracted', hoặc đã dừng). */
  async function checkDone() {
    if (finished) return true
    try {
      const next = await deps.getDossierStructure(dossierId, controller.signal)
      if (next.latestJobStatus !== 'extracted') finish(next)
    } catch (cause) {
      // Hồ sơ bị xoá hoặc bị thu quyền: hỏi lại cũng vô ích.
      if (
        !finished &&
        cause instanceof ApiError &&
        (cause.status === 403 || cause.status === 404)
      ) {
        stop()
        handlers.onGone?.()
        return true
      }
      // Lỗi mạng tạm thời: lần hỏi sau thử lại.
    }
    return finished
  }

  function schedulePoll() {
    if (finished) return
    clearTimeout(pollTimer)
    pollTimer = setTimeout(() => {
      void checkDone().then((done) => {
        if (!done) schedulePoll()
      })
    }, pollMs)
  }

  async function start() {
    // Tìm run mỗi lần bắt đầu theo dõi, không giữ run cũ: "Chạy lại" có thể đã
    // tạo lượt mới.
    let runId: string | null = null
    try {
      runId = await deps.findLatestRunId(dossierId, controller.signal)
    } catch {
      runId = null
    }
    if (finished) return
    if (!runId) {
      // Không có run (hoặc lỗi mạng): vẫn đếm 10 phút để còn báo khi kẹt.
      armStall(`dossier:${dossierId}`)
      schedulePoll()
      return
    }
    armStall(runId)
    try {
      for (const row of await deps.listRunSteps(runId, controller.signal)) {
        steps[row.step] = row
      }
      if (!finished) handlers.onPercent(ai2ProgressPercent({ ...steps }))
    } catch {
      // Không có số liệu bước: banner vẫn báo đang phân tích, chỉ thiếu %.
    }
    // AI2 có thể đã xong trong lúc trang đang mở.
    if (await checkDone()) return
    await deps.watchRun(
      runId,
      {
        onEvent: (event) => {
          const step = stepFromEvent(event)
          if (step) {
            steps[step.step] = step
            if (!finished) handlers.onPercent(ai2ProgressPercent({ ...steps }))
          }
          if (
            event.event === 'run.status_changed' ||
            event.event === 'run.completed'
          ) {
            void checkDone()
          }
        },
        onLost: () => {
          void checkDone()
        },
        onRejected: () => schedulePoll(),
      },
      stream.signal,
    )
    // Stream đóng (run xong, bị từ chối, hoặc quá 10 phút) mà job chưa rời
    // 'extracted': hỏi thưa tới khi rời.
    if (!(await checkDone())) schedulePoll()
  }

  void start()
  return stop
}
