import { relationLabel, reviewStateLabel } from '../../structure/displayLabels'
import {
  relationBadgeClasses,
  relationDotClasses,
  relationTone,
} from './relationTone'

/** Loại quan hệ, cùng màu với đường nối trên sơ đồ. */
export function RelationBadge({ label }: { label: string }) {
  const tone = relationTone(label)
  return (
    <span
      className={`inline-flex items-center gap-space-xs rounded-full px-space-sm py-0.5 font-label-sm text-label-sm font-semibold ring-1 ${relationBadgeClasses[tone]}`}
    >
      <span
        aria-hidden
        className={`h-1.5 w-1.5 rounded-full ${relationDotClasses[tone]}`}
      />
      {relationLabel(label)}
    </span>
  )
}

/** Nhãn trạng thái rà soát: AI đề xuất thì vàng, đã xác nhận thì xanh. */
export function ReviewBadge({ state }: { state: string }) {
  const needsReview = state === 'NEEDS_REVIEW'
  return (
    <span
      className={`rounded-full px-space-sm py-0.5 font-label-sm text-label-sm font-semibold ${
        needsReview
          ? 'bg-amber-50 text-amber-900'
          : state === 'PASS'
            ? 'bg-emerald-50 text-emerald-800'
            : 'bg-surface-container text-on-surface-variant'
      }`}
    >
      {needsReview ? 'cần rà soát' : reviewStateLabel(state)}
    </span>
  )
}
