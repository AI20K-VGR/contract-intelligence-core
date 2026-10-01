/**
 * Mức tin cậy của một vùng OCR hoặc một fact IDP.
 *
 * Ngưỡng khớp với ai-service/src/contract_ocr/reconstruction/config.py:
 * >= 0.95 tự chấp nhận, 0.85–0.95 nên xem, < 0.85 bắt buộc review.
 * Đây là ngưỡng tạm; chỉnh lại khi đã hiệu chỉnh trên ground truth.
 */
export const AUTO_ACCEPT_THRESHOLD = 0.95
export const REVIEW_THRESHOLD = 0.85

export type ConfidenceLevel = 'high' | 'medium' | 'low'

export function asConfidence(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
    ? value
    : null
}

export function confidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= AUTO_ACCEPT_THRESHOLD) return 'high'
  if (confidence >= REVIEW_THRESHOLD) return 'medium'
  return 'low'
}

export function needsReview(confidence: number | null | undefined) {
  return typeof confidence === 'number' && confidence < REVIEW_THRESHOLD
}

/** 0.974 → "97%". Làm tròn xuống để không hiện cao hơn thực tế. */
export function formatConfidence(confidence: number) {
  // Sai số dấu phẩy động: 0.29 * 100 = 28.999…
  return `${Math.floor(confidence * 100 + 1e-9)}%`
}

/** Vùng gộp nhiều dòng tin cậy bằng dòng yếu nhất của nó. */
export function weakestConfidence(values: (number | null | undefined)[]) {
  const known = values.filter((value): value is number => typeof value === 'number')
  return known.length > 0 ? Math.min(...known) : null
}

export const confidenceLabels: Record<ConfidenceLevel, string> = {
  high: 'Tin được',
  medium: 'Nên xem',
  low: 'Cần review',
}

export const confidenceBoxClasses: Record<ConfidenceLevel, string> = {
  high: 'border-emerald-600 bg-emerald-300/30',
  medium: 'border-amber-500 bg-amber-300/40',
  low: 'border-red-600 bg-red-300/40',
}

export const confidenceBadgeClasses: Record<ConfidenceLevel, string> = {
  high: 'bg-emerald-600 text-white',
  medium: 'bg-amber-500 text-black',
  low: 'bg-red-600 text-white',
}
