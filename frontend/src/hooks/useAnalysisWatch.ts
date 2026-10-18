import { useEffect, useRef, useState } from 'react'
import { startAnalysisWatch } from '../api/analysisWatch'
import type { DossierStructure } from '../api/structure'

/**
 * Hồ sơ đang phân tích (job 'extracted'): theo dõi AI2 (`startAnalysisWatch`)
 * và gọi onDone một lần khi job rời 'extracted' (AI2 xong, lỗi hoặc bị huỷ) để
 * trang tải lại kết quả.
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
  // "Kiểm tra lại" đặt lại mốc 10 phút; lần theo dõi thường thì tính tiếp mốc cũ.
  const restartNext = useRef(false)

  useEffect(() => {
    if (!dossierId || !running) {
      setPercent(null)
      setStalled(false)
      return
    }
    setStalled(false)
    const restart = restartNext.current
    restartNext.current = false
    return startAnalysisWatch(
      dossierId,
      {
        onPercent: setPercent,
        onStalled: () => setStalled(true),
        onDone: (next) => latest.current(next),
      },
      { restart },
    )
  }, [dossierId, running, watchKey])

  return {
    percent,
    /** Quá 10 phút mà AI2 chưa xong: SSE đã đóng, vẫn hỏi lại 60 giây một lần. */
    stalled,
    /** Hỏi lại ngay, nối lại SSE và tính lại mốc 10 phút (nút "Kiểm tra lại"). */
    recheck: () => {
      restartNext.current = true
      setWatchKey((key) => key + 1)
    },
  }
}
