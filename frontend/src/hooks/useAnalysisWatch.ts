import { useEffect, useRef, useState } from 'react'
import {
  ai2ProgressPercent,
  findLatestRunId,
  listRunSteps,
} from '../api/runEvents'
import { getDossierStructure, type DossierStructure } from '../api/structure'

const ANALYSIS_POLL_MS = 5000

/**
 * Hồ sơ đang phân tích (job 'extracted'): hỏi lại định kỳ và gọi onDone một
 * lần khi job rời 'extracted' (AI2 xong hoặc lỗi), để trang tải lại kết quả.
 * Trả % AI2 đã xong theo các bước BE ghi; null khi chưa có số liệu.
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

  useEffect(() => {
    if (!dossierId || !running) {
      setPercent(null)
      return
    }
    const controller = new AbortController()
    let timer: number | undefined
    let runId: string | null = null

    function schedule() {
      timer = window.setTimeout(() => void check(), ANALYSIS_POLL_MS)
    }

    async function syncPercent() {
      try {
        runId ??= await findLatestRunId(dossierId, controller.signal)
        if (!runId || controller.signal.aborted) return
        const rows = await listRunSteps(runId, controller.signal)
        if (controller.signal.aborted) return
        setPercent(
          ai2ProgressPercent(
            Object.fromEntries(rows.map((row) => [row.step, row])),
          ),
        )
      } catch {
        // Không có số liệu bước: banner vẫn báo đang phân tích, chỉ thiếu %.
      }
    }

    async function check() {
      try {
        const next = await getDossierStructure(dossierId, controller.signal)
        if (controller.signal.aborted) return
        if (next.latestJobStatus !== 'extracted') {
          latest.current(next)
          return
        }
        await syncPercent()
      } catch {
        // Lỗi mạng tạm thời: lần hỏi sau thử lại.
      }
      if (controller.signal.aborted) return
      schedule()
    }

    void syncPercent()
    schedule()
    return () => {
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [dossierId, running])

  return { percent }
}
