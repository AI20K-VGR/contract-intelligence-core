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
  const [gone, setGone] = useState(false)
  const [watchKey, setWatchKey] = useState(0)
  // "Kiểm tra lại" đặt lại mốc 10 phút; lần theo dõi thường thì tính tiếp mốc cũ.
  // Giữ mã hồ sơ đã bấm: đổi sang hồ sơ khác thì cờ không áp vào hồ sơ đó.
  const restartNext = useRef<string | null>(null)

  useEffect(() => {
    if (!dossierId || !running) {
      setPercent(null)
      setStalled(false)
      return
    }
    setStalled(false)
    setGone(false)
    const restart = restartNext.current === dossierId
    restartNext.current = null
    return startAnalysisWatch(
      dossierId,
      {
        onPercent: setPercent,
        onStalled: () => setStalled(true),
        onDone: (next) => latest.current(next),
        onGone: () => setGone(true),
      },
      { restart },
    )
  }, [dossierId, running, watchKey])

  return {
    percent,
    /** Quá 10 phút mà AI2 chưa xong: SSE đã đóng, vẫn hỏi lại 60 giây một lần. */
    stalled,
    /** Hồ sơ không còn mở được (403/404): đã ngừng theo dõi. */
    gone,
    /**
     * Lần theo dõi tới tính mốc 10 phút từ đầu. Gọi khi bấm "Chạy lại":
     * /ai2/retry dùng lại run cũ, nên mốc cũ của run đó không còn đúng.
     */
    restartClock: () => {
      restartNext.current = dossierId
    },
    /** Hỏi lại ngay, nối lại SSE và tính lại mốc 10 phút (nút "Kiểm tra lại"). */
    recheck: () => {
      restartNext.current = dossierId
      setWatchKey((key) => key + 1)
    },
  }
}
