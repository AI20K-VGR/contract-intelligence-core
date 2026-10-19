// Màu theo loại quan hệ, dùng chung cho nhãn trong danh sách và đường nối trên
// sơ đồ: cùng một loại thì cùng một màu ở mọi chỗ.

export type RelationTone =
  'reference' | 'conflict' | 'duplicate' | 'scope' | 'add' | 'remove' | 'other'

const TONE_BY_LABEL: Record<string, RelationTone> = {
  REFERENCE: 'reference',
  REFERENCES: 'reference',
  AMENDS: 'reference',
  CONFLICT: 'conflict',
  CONFLICT_CANDIDATE: 'conflict',
  DUPLICATE: 'duplicate',
  SUBSTITUTION: 'duplicate',
  GENERAL_SPECIFIC: 'scope',
  GENERAL_VS_SPECIFIC: 'scope',
  SCOPE_LIMIT: 'scope',
  INSERTION: 'add',
  REPEAL: 'remove',
  REJECTION: 'remove',
}

export function relationTone(code: string): RelationTone {
  return TONE_BY_LABEL[code.trim().toUpperCase()] ?? 'other'
}

/** Nhãn loại quan hệ (chip trong danh sách, bộ lọc). */
export const relationBadgeClasses: Record<RelationTone, string> = {
  reference: 'bg-brand-50 text-brand-700 ring-brand-200',
  conflict: 'bg-error-container text-on-error-container ring-error/30',
  duplicate: 'bg-amber-50 text-amber-900 ring-amber-200',
  scope: 'bg-violet-50 text-violet-800 ring-violet-200',
  add: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  remove: 'bg-rose-50 text-rose-800 ring-rose-200',
  other: 'bg-surface-container text-on-surface-variant ring-outline-variant',
}

/** Chấm màu đứng trước tên loại quan hệ. */
export const relationDotClasses: Record<RelationTone, string> = {
  reference: 'bg-brand-500',
  conflict: 'bg-error',
  duplicate: 'bg-amber-500',
  scope: 'bg-violet-500',
  add: 'bg-emerald-500',
  remove: 'bg-rose-500',
  other: 'bg-outline',
}

/** Đường nối và mũi tên trên sơ đồ. */
export const relationStrokeClasses: Record<RelationTone, string> = {
  reference: 'stroke-brand-500',
  conflict: 'stroke-error',
  duplicate: 'stroke-amber-500',
  scope: 'stroke-violet-500',
  add: 'stroke-emerald-500',
  remove: 'stroke-rose-500',
  other: 'stroke-outline',
}

export const relationFillClasses: Record<RelationTone, string> = {
  reference: 'fill-brand-500',
  conflict: 'fill-error',
  duplicate: 'fill-amber-500',
  scope: 'fill-violet-500',
  add: 'fill-emerald-500',
  remove: 'fill-rose-500',
  other: 'fill-outline',
}

export const RELATION_TONES: RelationTone[] = [
  'reference',
  'conflict',
  'duplicate',
  'scope',
  'add',
  'remove',
  'other',
]
