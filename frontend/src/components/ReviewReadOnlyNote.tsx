import { MaterialIcon } from './icons'

/** Thay khối chọn Đúng/Sai cho vai trò chỉ xem được kết quả thẩm định. */
export function ReviewReadOnlyNote({ reason }: { reason: string | null }) {
  return (
    <p className="mt-1 flex items-start gap-1 rounded bg-surface-container-low p-2 font-body-sm text-body-sm text-on-surface-variant">
      <MaterialIcon name="visibility" className="mt-0.5 shrink-0 text-[15px]" />
      <span>Bạn xem được kết quả và lịch sử thẩm định. {reason}</span>
    </p>
  )
}
