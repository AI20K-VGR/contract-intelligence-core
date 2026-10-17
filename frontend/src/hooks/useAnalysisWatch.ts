import { useEffect, useRef, useState } from 'react'
import {
  ai2ProgressPercent,
  findLatestRunId,
  listRunSteps,
  stepFromEvent,
  watchRun,
  type RunStep,
} from '../api/runEvents'
import { getDossierStructure, type DossierStructure } from '../api/structure'

/**
 * Hồ sơ phân tích xong dưới 10 phút. Quá mốc này mà job vẫn ở 'extracted' thì
 * báo người dùng (có thể kẹt, ví dụ worker dừng giữa chừng), đóng SSE và chỉ
 * hỏi lại thưa, để AI2 xong muộn thì trang vẫn tự mở. Backend tự đánh 'failed'
 * khi AI2 quá hạn, nên đây chỉ là lưới an toàn.
 */
export const ANALYSIS_STALL_MS = 10 * 60 * 1000

// SSE bị từ chối, hoặc stream đã đóng mà job chưa rời 'extracted': hỏi thưa.
const FALLBACK_POLL_MS = 15000
// Đã quá 10 phút: hỏi thưa hơn nữa, tới khi job rời 'extracted'.
const STALLED_POLL_MS = 60000

/**
 * Hồ sơ đang phân tích (job 'extracted'): nghe SSE `step.changed` của run để
 * cập nhật % AI2, và gọi onDone một lần khi job rời 'extracted' (AI2 xong hoặc
 * lỗi) để trang tải lại kết quả. Chỉ hỏi lại hồ sơ khi run đổi trạng thái hoặc
 * SSE mất kết nối, không hỏi định kỳ.
 */
export function useAnalysisWatch(
  dossierId: string,
  running: boolean,
  onDone: (next: DossierStructure) => void,
) {
  const latest = useRef(onDone)
  useEffect(() => {
    latest.current = onDone
  })
  const [percent, setPercent] = useState<number | null>(null)
  const [stalled, setStalled] = useState(false)
  const [watchKey, setWatchKey] = useState(0)

  useEffect(() => {
    if (!dossierId || !running) {
      setPercent(null)
      setStalled(false)
      return
    }
    setStalled(false)
    // controller: cả lần theo dõi (rời trang thì huỷ). stream: riêng SSE, đóng
    // khi quá 10 phút; việc hỏi thưa vẫn chạy tiếp.
    const controller = new AbortController()
    const stream = new AbortController()
    let finished = false
    let pollTimer: number | undefined
    let pollMs = FALLBACK_POLL_MS
    const steps: Record<string, RunStep> = {}

    const stallTimer = window.setTimeout(() => {
      if (finished) return
      pollMs = STALLED_POLL_MS
      stream.abort()
      setStalled(true)
      schedulePoll()
    }, ANALYSIS_STALL_MS)

    function finish(next: DossierStructure) {
      if (finished) return
      finished = true
      window.clearTimeout(stallTimer)
      window.clearTimeout(pollTimer)
      stream.abort()
      controller.abort()
      latest.current(next)
    }

    /** true khi đã ngừng theo dõi (job rời 'extracted', hoặc rời trang). */
    async function checkDone() {
      if (finished) return true
      try {
        const next = await getDossierStructure(dossierId, controller.signal)
        if (next.latestJobStatus !== 'extracted') finish(next)
      } catch {
        // Lỗi mạng tạm thời: lần hỏi sau thử lại.
      }
      return finished
    }

    function schedulePoll() {
      if (finished) return
      window.clearTimeout(pollTimer)
      pollTimer = window.setTimeout(() => {
        void checkDone().then((done) => {
          if (!done) schedulePoll()
        })
      }, pollMs)
    }

    async function start() {
      // Tìm run mỗi lần bắt đầu theo dõi, không giữ run cũ: "Phân tích lại"
      // hay "Chạy lại toàn bộ" có thể đã tạo lượt mới.
      let runId: string | null = null
      try {
        runId = await findLatestRunId(dossierId, controller.signal)
      } catch {
        runId = null
      }
      if (finished) return
      if (!runId) {
        schedulePoll()
        return
      }
      try {
        for (const row of await listRunSteps(runId, controller.signal)) {
          steps[row.step] = row
        }
        if (!finished) setPercent(ai2ProgressPercent({ ...steps }))
      } catch {
        // Không có số liệu bước: banner vẫn báo đang phân tích, chỉ thiếu %.
      }
      // AI2 có thể đã xong trong lúc trang đang mở.
      if (await checkDone()) return
      await watchRun(
        runId,
        {
          onEvent: (event) => {
            const step = stepFromEvent(event)
            if (step) {
              steps[step.step] = step
              setPercent(ai2ProgressPercent({ ...steps }))
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
    return () => {
      finished = true
      stream.abort()
      controller.abort()
      window.clearTimeout(stallTimer)
      window.clearTimeout(pollTimer)
    }
  }, [dossierId, running, watchKey])

  return {
    percent,
    /** Quá 10 phút mà AI2 chưa xong: SSE đã đóng, vẫn hỏi lại 60 giây một lần. */
    stalled,
    /** Hỏi lại ngay và nối lại SSE (nút "Kiểm tra lại"), thêm 10 phút nữa. */
    recheck: () => setWatchKey((key) => key + 1),
  }
}
