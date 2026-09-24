import type { ClauseNode, ClauseRegion } from '../api/structure'

/**
 * Loại cấu trúc người dùng chọn khi tải lên.
 * - numbered: tài liệu có Điều / Khoản / Điểm (hoặc 1. / 1.1 / a) ...).
 * - freeform: tài liệu tự do, phân cấp theo tiêu đề (cỡ chữ, viết hoa, khoảng trống).
 */
export type StructureMode = 'numbered' | 'freeform' | 'tables'

export const STRUCTURE_MODE_KEY = 'structure_mode'

export const structureModes: {
  value: StructureMode
  label: string
  /** Nhãn gọn cho thanh công cụ. */
  short: string
  icon: string
  hint: string
}[] = [
  {
    value: 'numbered',
    label: 'Cấu trúc Điều / Khoản / Điểm',
    short: 'Điều / Khoản / Điểm',
    icon: 'format_list_numbered',
    hint: 'Hợp đồng, quy chế đánh số: Điều 1, Khoản 1, 1.1, a), (i)…',
  },
  {
    value: 'freeform',
    label: 'Cấu trúc tự do',
    short: 'Tự do',
    icon: 'segment',
    hint: 'Văn bản không đánh số. Phân cấp theo tiêu đề in lớn, viết hoa.',
  },
  {
    value: 'tables',
    label: 'Bảng',
    short: 'Bảng',
    icon: 'table',
    hint: 'Hiện mọi bảng mà OCR đã trích từ hợp đồng.',
  },
]

export function parseStructureMode(value: unknown): StructureMode | null {
  return value === 'numbered' || value === 'freeform' || value === 'tables'
    ? value
    : null
}

/** Kiểu xem cây cấu trúc (cùng dữ liệu, khác cách trình bày). */
export type StructureView = 'mindmap' | 'tree' | 'outline' | 'document'

export const STRUCTURE_VIEW_KEY = 'structure_view'

export const structureViews: {
  value: StructureView
  label: string
  icon: string
  hint: string
}[] = [
  {
    value: 'mindmap',
    label: 'Sơ đồ',
    icon: 'account_tree',
    hint: 'Sơ đồ tư duy: gốc bên trái, nhánh rẽ sang phải.',
  },
  {
    value: 'tree',
    label: 'Cây dọc',
    icon: 'lan',
    hint: 'Cây từ trên xuống: gốc trên cùng, các cấp xoè xuống dưới.',
  },
  {
    value: 'outline',
    label: 'Dàn bài',
    icon: 'format_list_bulleted',
    hint: 'Cây dọc thụt đầu dòng, mở/thu từng nút, lọc nhanh.',
  },
  {
    value: 'document',
    label: 'Văn bản',
    icon: 'article',
    hint: 'Mục lục bên trái, toàn văn theo cấu trúc bên phải.',
  },
]

export function parseStructureView(value: unknown): StructureView | null {
  return value === 'mindmap' ||
    value === 'tree' ||
    value === 'outline' ||
    value === 'document'
    ? value
    : null
}

export function structureModeLabel(mode: StructureMode) {
  return structureModes.find((item) => item.value === mode)?.label ?? mode
}

/** Một dòng OCR thô từ GET /api/v1/pages/{page_id}. */
export type OcrLine = {
  id: string
  pageNo: number
  lineNo: number
  text: string
  /** [x1, y1, x2, y2] chuẩn hóa 0..1 theo trang. null nếu OCR không có tọa độ. */
  bbox: [number, number, number, number] | null
  pageWidth: number
  pageHeight: number
}

/** Một nút mở mới trong cây, trước khi gắn cha con. */
export type OpenNode = {
  id: string
  /** Số càng nhỏ càng cao trong cây. */
  level: number
  nodeType: string
  label: string
  number: string | null
  title: string | null
  text: string
  pageNo: number
  regions?: ClauseRegion[]
}

export type { ClauseNode, ClauseRegion }
