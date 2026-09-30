import { useEffect, useState } from 'react'
import type { ReviewSpot } from '../api/structure'
import { reviewerLabel } from '../review/reviewerLabel'
import {
  VERDICT_LABEL,
  conflictSignature,
  conflictState,
} from '../structure/conflictAnchors'
import { MaterialIcon } from './icons'

/*
 * Banner dính ở đầu panel trích dẫn khi điều khoản đang xem có xung đột.
 * Không tự tắt. Bấm X: ẩn cho nút này trong phiên làm việc; có thẩm định mới
 * hoặc chạy lại phân tích thì chữ ký đổi và banner hiện lại. Bấm vào banner:
 * mở trang đối soát đúng xung đột đó.
 */

const STORE_PREFIX = 'conflict-notice:'

function storageKey(dossierId: string, nodeId: string, spots: ReviewSpot[]) {
  return `${STORE_PREFIX}${dossierId}:${nodeId}:${conflictSignature(spots)}`
}

function readDismissed(key: string) {
  try {
    return window.sessionStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

function writeDismissed(key: string) {
  try {
    window.sessionStorage.setItem(key, '1')
  } catch {
    // Không lưu được thì banner chỉ ẩn trong lần hiển thị này.
  }
}

function annexLabel(spot: ReviewSpot, documentId: string | null) {
  const other = spot.sides.find((side) => side.documentId !== documentId)
  const label = other?.label.trim().toLowerCase() ?? ''
  if (label === 'annex' || label === 'b') return 'phụ lục'
  if (label === 'contract' || label === 'a') return 'hợp đồng'
  return other?.label.trim() ? other.label.trim() : 'tài liệu khác'
}

export function spotStatusText(spot: ReviewSpot) {
  const latest = spot.review?.latest ?? null
  if (!latest) return 'Chưa ai thẩm định, vui lòng kiểm tra lại.'
  const when = latest.reviewedAt
    ? new Date(latest.reviewedAt).toLocaleString('vi-VN')
    : ''
  const verdict = VERDICT_LABEL[latest.action] ?? latest.action
  const who = reviewerLabel(latest)
  if (conflictState(spot) === 'dismissed') {
    return `${who} đã thẩm định sai${when ? ` lúc ${when}` : ''}: máy báo xung đột này không đúng.`
  }
  return `Đã được ${who} thẩm định ${verdict}${when ? ` lúc ${when}` : ''}.`
}

export function ConflictNotice({
  dossierId,
  documentId,
  nodeId,
  spots,
  onOpen,
}: {
  dossierId: string
  documentId: string | null
  nodeId: string
  spots: ReviewSpot[]
  onOpen: (findingId: string) => void
}) {
  const key = storageKey(dossierId, nodeId, spots)
  const [dismissed, setDismissed] = useState(() => readDismissed(key))

  useEffect(() => {
    setDismissed(readDismissed(key))
  }, [key])

  if (spots.length === 0 || dismissed) return null

  const open = spots.filter((spot) => conflictState(spot) === 'open').length
  const heading =
    spots.length === 1
      ? `Trích dẫn này có xung đột với ${annexLabel(spots[0], documentId)}`
      : `Trích dẫn này có ${spots.length} xung đột với ${annexLabel(spots[0], documentId)}`

  return (
    <div
      className="flex shrink-0 items-start gap-2 border-b border-amber-300 bg-amber-50 px-4 py-2 text-amber-950"
      data-conflict-notice
      role="status"
    >
      <MaterialIcon name="warning" className="mt-0.5 shrink-0 text-[18px] text-amber-600" />
      <div className="min-w-0 flex-1">
        <button
          className="block w-full text-left"
          type="button"
          onClick={() => onOpen(spots[0].id)}
        >
          <span className="block font-body-sm text-body-sm font-semibold">
            {heading}
            {open > 0 && spots.length > 1 ? ` · ${open} chưa thẩm định` : ''}
          </span>
        </button>
        <ul className="mt-0.5 flex flex-col gap-0.5">
          {spots.slice(0, 3).map((spot) => (
            <li key={spot.id}>
              <button
                className="group flex w-full items-start gap-1 text-left font-body-sm text-body-sm text-amber-900 hover:text-amber-950 hover:underline"
                type="button"
                onClick={() => onOpen(spot.id)}
              >
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{spot.topic}</span>
                  {' — '}
                  {spotStatusText(spot)}
                </span>
                <MaterialIcon
                  name="open_in_new"
                  className="mt-0.5 shrink-0 text-[14px] opacity-60 group-hover:opacity-100"
                />
              </button>
            </li>
          ))}
          {spots.length > 3 ? (
            <li className="font-body-sm text-body-sm text-amber-900">
              và {spots.length - 3} xung đột khác. Bấm để xem trang đối soát.
            </li>
          ) : null}
        </ul>
      </div>
      <button
        aria-label="Tắt thông báo xung đột"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-amber-800 hover:bg-amber-100"
        title="Tắt thông báo cho điều khoản này trong phiên làm việc"
        type="button"
        onClick={() => {
          writeDismissed(key)
          setDismissed(true)
        }}
      >
        <MaterialIcon name="close" className="text-[18px]" />
      </button>
    </div>
  )
}
