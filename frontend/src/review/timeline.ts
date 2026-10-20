import { reviewerLabel } from './reviewerLabel'

/*
 * Hai phần thẩm định trả lời hai câu hỏi khác nhau: trích dẫn có đúng chỗ
 * không, và xung đột máy báo có thật không. Chúng không gộp kết luận, chỉ
 * gộp dòng thời gian theo vị trí để ai xem ở đâu cũng thấy đủ ai đã làm gì.
 */

export type TimelineKind = 'finding' | 'citation'

export type TimelineEntry = {
  key: string
  kind: TimelineKind
  /** Nguồn: "Hợp đồng", "Phụ lục" hoặc chủ đề xung đột. */
  source: string
  action: string
  who: string
  when: string | null
  note: string
}

export const KIND_LABEL: Record<TimelineKind, string> = {
  finding: 'Thẩm định xung đột',
  citation: 'Thẩm định trích dẫn',
}

export const ACTION_LABEL: Record<string, string> = {
  confirm: 'Đúng',
  reject: 'Sai',
  correct: 'Đúng (có bổ sung)',
}

export function actionLabel(action: string) {
  return ACTION_LABEL[action] ?? action
}

type EntryLike = {
  revisionNumber: number
  action: string
  comment: string | null
  assessment: string | null
  reviewerId: string
  reviewerName: string | null
  reviewerEmail: string | null
  createdAt: string | null
}

export function timelineEntries(
  kind: TimelineKind,
  source: string,
  keyPrefix: string,
  history: EntryLike[],
): TimelineEntry[] {
  return history.map((entry) => ({
    key: `${keyPrefix}:${entry.revisionNumber}`,
    kind,
    source,
    action: entry.action,
    who: reviewerLabel(entry),
    when: entry.createdAt,
    note: (entry.assessment ?? entry.comment ?? '').trim(),
  }))
}

function stamp(value: string | null) {
  if (!value) return 0
  const time = new Date(value).getTime()
  return Number.isFinite(time) ? time : 0
}

/** Mới nhất lên đầu; cùng thời điểm thì giữ thứ tự đưa vào. */
export function mergeTimelines(...groups: TimelineEntry[][]): TimelineEntry[] {
  const all = groups.flat().map((entry, index) => ({ entry, index }))
  all.sort((a, b) => {
    const delta = stamp(b.entry.when) - stamp(a.entry.when)
    return delta !== 0 ? delta : a.index - b.index
  })
  return all.map((item) => item.entry)
}

export function formatWhen(value: string | null) {
  return value ? new Date(value).toLocaleString('vi-VN') : ''
}
