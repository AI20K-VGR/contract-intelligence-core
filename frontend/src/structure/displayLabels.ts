// Bảng dịch mã hệ thống (AI1/AI2) sang chữ người dùng đọc được.
// Mã lạ không hiện nguyên văn: trả câu chung, còn mã gốc ghi Console qua TechnicalDetail.

/** Loại quan hệ giữa điều khoản (PairLabel, EdgeOp của AI2). */
const RELATION_LABELS: Record<string, string> = {
  REFERENCE: 'Dẫn chiếu',
  REFERENCES: 'Dẫn chiếu',
  CONFLICT: 'Có thể mâu thuẫn',
  CONFLICT_CANDIDATE: 'Có thể mâu thuẫn',
  DUPLICATE: 'Trùng lặp',
  GENERAL_SPECIFIC: 'Quy định chung – riêng',
  GENERAL_VS_SPECIFIC: 'Quy định chung – riêng',
  AMENDS: 'Sửa đổi',
  INSERTION: 'Bổ sung',
  SUBSTITUTION: 'Thay thế',
  REPEAL: 'Bãi bỏ',
  REJECTION: 'Không áp dụng',
  SCOPE_LIMIT: 'Giới hạn phạm vi',
}

export function relationLabel(code: string) {
  return RELATION_LABELS[code.trim().toUpperCase()] ?? 'Quan hệ khác'
}

/** Trạng thái rà soát (ReviewState của AI2). */
const REVIEW_STATE_LABELS: Record<string, string> = {
  PASS: 'Đã xác nhận',
  NEEDS_REVIEW: 'Cần rà soát',
  INSUFFICIENT_EVIDENCE: 'Chưa đủ căn cứ',
  BLOCKED: 'Bị chặn',
  ANSWERED: 'Đã trả lời',
  NOT_COMPARABLE: 'Không so sánh được',
  NOT_MEASURED: 'Chưa đo',
  NOT_READY: 'Chưa sẵn sàng',
}

export function reviewStateLabel(code: string) {
  return REVIEW_STATE_LABELS[code.trim().toUpperCase()] ?? 'Chưa rõ trạng thái'
}

/** Mức độ phân tích (coverage.state) và trạng thái kiểm chứng trích dẫn. */
const STATE_LABELS: Record<string, string> = {
  COMPLETE: 'Đầy đủ',
  PARTIAL: 'Một phần',
  NONE: 'Chưa có',
  EMPTY: 'Chưa có',
  NOT_RUN: 'Chưa chạy',
  SKIPPED: 'Đã bỏ qua',
  FAILED: 'Bị lỗi',
  VERIFIED: 'Đã đối chiếu khớp',
  UNVERIFIED: 'Chưa đối chiếu được',
  LOCATABLE: 'Đã định vị nguồn',
  UNRESOLVED: 'Chưa định vị được nguồn',
}

export function stateLabel(code: string) {
  return STATE_LABELS[code.trim().toUpperCase()] ?? 'Chưa rõ'
}

/** Vấn đề về căn cứ (EvidenceIssue.code) có ý nghĩa với người dùng. */
const ISSUE_LABELS: Record<string, string> = {
  INSUFFICIENT_EVIDENCE: 'Chưa đủ căn cứ trong hồ sơ',
  NODE_TEXT_UNGROUNDED: 'Có đoạn chưa khớp với tài liệu gốc',
  PAGE_FAILED: 'Có trang chưa đọc được',
  PAGE_PARTIAL: 'Có trang chỉ đọc được một phần',
  PAGE_QUALITY: 'Có trang chất lượng thấp',
  PAGE_BLANK_UNVERIFIED: 'Có trang trống chưa được xác nhận',
  PAGE_BLANK_VERIFIED: 'Có trang trống',
  PAGE_COUNT_MISMATCH: 'Số trang không khớp với tệp gốc',
  ORIENTATION_METADATA_REVIEW: 'Có trang bị xoay, cần kiểm tra',
  AMBIGUOUS_HEADING_AS_BLOCK: 'Có tiêu đề chưa rõ thuộc điều khoản nào',
  CONTRACT_UNIT_BOUNDARY_AMBIGUOUS: 'Ranh giới giữa các điều khoản chưa rõ',
  CONTRACT_UNITS_DERIVED: 'Cấu trúc điều khoản được suy ra, cần kiểm tra',
  STRUCTURE_ROOT_DERIVED: 'Cấu trúc điều khoản được suy ra, cần kiểm tra',
  LEGACY_TEXT_ONLY: 'Tài liệu chỉ có chữ, không có vị trí trên trang',
  BUDGET_EXCEEDED: 'Hồ sơ quá dài, chỉ phân tích được một phần',
  EMBEDDING_BUDGET_EXCEEDED: 'Hồ sơ quá dài, chỉ phân tích được một phần',
  EGRESS_DENIED: 'Hồ sơ chưa được phép gửi tới dịch vụ AI',
  PROCESSING_TIMEOUT: 'Phân tích quá lâu nên dừng giữa chừng',
  EXTRACTION_FAILED: 'Chưa trích xuất được dữ kiện',
  GRAPH_BUILD_FAILED: 'Chưa tìm được quan hệ giữa điều khoản',
  PAIR_BUILD_FAILED: 'Chưa tìm được quan hệ giữa điều khoản',
}

export function issueLabel(code: string) {
  return (
    ISSUE_LABELS[code.trim().toUpperCase()] ??
    'Có điểm cần kiểm tra khi phân tích hồ sơ'
  )
}

/** Lý do của phát hiện theo ngữ cảnh (reason_code khi hỏi đáp). */
const REASON_LABELS: Record<string, string> = {
  INSUFFICIENT_EVIDENCE: 'Chưa đủ căn cứ',
  SAME_CLAUSE: 'Cùng một điều khoản',
  SAME_VALUE: 'Cùng giá trị',
  AMENDS: 'Bị sửa đổi',
  STRUCTURAL_NODE: 'Là tiêu đề, không phải nội dung',
  UNNUMBERED_BLOCK: 'Đoạn chưa đánh số',
  BUDGET_EXCEEDED: 'Hồ sơ quá dài, chỉ xét được một phần',
  EXPIRED: 'Đã hết hiệu lực',
}

export function reasonLabel(code: string) {
  return REASON_LABELS[code.trim().toUpperCase()] ?? 'Phát hiện cần xem lại'
}

function pick(table: Record<string, string>, fallback: string) {
  return (code: string | null | undefined) =>
    table[(code ?? '').trim().toUpperCase()] ?? fallback
}

/** Nhóm điều khoản (family) của kết quả phân tích ngữ nghĩa. */
export const familyLabel = pick(
  {
    OBLIGATION: 'Nghĩa vụ',
    PARAMETER: 'Thông số',
    REMEDY: 'Chế tài, khắc phục',
    DEFINITION: 'Định nghĩa',
  },
  'Điều khoản khác',
)

/** Trạng thái giá trị của một trường trong điều khoản. */
export const slotStateLabel = pick(
  {
    GROUNDED: 'Có căn cứ',
    UNKNOWN: 'Chưa rõ',
    ABSENT: 'Không có trong điều khoản',
    UNSUPPORTED: 'Chưa hỗ trợ',
  },
  'Chưa rõ',
)

/** Mức chắc chắn khi ghép điều khoản. */
export const certaintyLabel = pick(
  { DEFINITE: 'Xác định rõ', UNKNOWN: 'Chưa chắc chắn' },
  'Chưa chắc chắn',
)

/** Kết luận khi so một cặp điều khoản. */
export const dispositionLabel = pick(
  {
    DUPLICATE: 'Trùng lặp',
    COMPARABLE_DIFFERENCE: 'Khác nhau',
    NOT_COMPARABLE: 'Không so sánh được',
    GENERAL_VS_SPECIFIC: 'Quy định chung – riêng',
    SCOPE_DIFFERS: 'Khác phạm vi áp dụng',
    NEEDS_REVIEW_UNPARSED: 'Cần rà soát (chưa đọc được nội dung)',
    NEEDS_REVIEW_BACKOFF: 'Cần rà soát',
    GRADUATED: 'Mức tăng dần theo bậc',
    CUMULATIVE: 'Cộng dồn',
    CONFLICT_CANDIDATE: 'Có thể mâu thuẫn',
  },
  'Cần rà soát',
)

/** Loại khác biệt trong một cặp nghi vấn. */
export const conflictKindLabel = pick(
  {
    SEMANTIC_CONFLICT: 'Mâu thuẫn nội dung',
    ARITHMETIC_INCONSISTENCY: 'Sai lệch số liệu',
    AMENDMENT_REVIEW: 'Cần xem lại sửa đổi',
    COMPARABLE_DIFFERENCE: 'Khác nhau',
  },
  'Khác nhau',
)

/** Loại ngày trên dòng thời gian. */
export const dateRoleLabel = pick(
  { EFFECTIVE: 'Ngày hiệu lực', SIGNING: 'Ngày ký', UNKNOWN: 'Ngày' },
  'Ngày',
)

/** Trạng thái kiểm chứng trích dẫn của kết quả ngữ nghĩa. */
export const validationLabel = pick(
  { VALID: 'Đã đối chiếu khớp tài liệu gốc' },
  'Chưa đối chiếu được với tài liệu gốc',
)

/** Mã dạng IN_HOA_GẠCH_DƯỚI là mã hệ thống, không phải câu chữ. */
export function isSystemCode(text: string) {
  return /^[A-Z0-9]+(?:_[A-Z0-9]+)+$/.test(text.trim())
}

/** Vai trò tài liệu trong hồ sơ. */
export function documentRoleLabel(role: string | null | undefined) {
  const value = (role ?? '').trim().toLowerCase()
  if (value === 'contract' || value === 'body') return 'Hợp đồng'
  if (value === 'annex') return 'Phụ lục'
  return 'Tài liệu'
}

/** "doc-p003-l0012" → 12. Mã dòng của AI1 luôn kết thúc bằng l<số>. */
function lineNumber(lineId: string) {
  const match = /l(\d+)$/i.exec(lineId.trim())
  return match ? Number(match[1]) : null
}

/** Danh sách mã dòng → "dòng 12" / "dòng 12–14" / "dòng 3, 9". */
export function linesLabel(lineIds: readonly string[]) {
  const numbers = [
    ...new Set(lineIds.map(lineNumber).filter((n): n is number => n !== null)),
  ].sort((a, b) => a - b)
  if (numbers.length === 0) return null
  if (numbers.length === 1) return `dòng ${numbers[0]}`
  const contiguous = numbers.every(
    (n, i) => i === 0 || n === numbers[i - 1]! + 1,
  )
  return contiguous
    ? `dòng ${numbers[0]}–${numbers[numbers.length - 1]}`
    : `dòng ${numbers.join(', ')}`
}

/** "doc-t002" → "Bảng 2"; "...:r003:c004" → "hàng 3, cột 4". */
export function tableCellLabel(
  tableId: string | null | undefined,
  cellId: string | null | undefined,
) {
  const table = /t(?:able_)?(\d+)$/i.exec(tableId ?? '')
  const row = /:r(\d+)/i.exec(cellId ?? '')
  const column = /:c(\d+)/i.exec(cellId ?? '')
  const parts = [
    table ? `Bảng ${Number(table[1])}` : 'Bảng',
    row
      ? `hàng ${Number(row[1])}`
      : /:header:/i.test(cellId ?? '')
        ? 'tiêu đề'
        : null,
    column ? `cột ${Number(column[1])}` : null,
  ]
  return parts.filter(Boolean).join(', ')
}
