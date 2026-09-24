/**
 * Nhận diện ký hiệu đánh số ở đầu dòng cho tài liệu Điều / Khoản / Điểm.
 *
 * Mỗi loại ký hiệu có một "level" cố định. Số càng nhỏ càng cao trong cây:
 *   0  Phần I
 *   1  Chương I / I.
 *   2  Mục 1 / A.
 *   3  Điều 1
 *   4  Khoản 1 / 1.
 *   5  1.1        (mỗi cấp thập phân sâu thêm +1)
 *   10 a) / (a) / 1)
 *   11 (i) / (ii)
 *   12 - / • / +
 *
 * Bộ dựng cây chỉ dựa vào level: ký hiệu mới có level L sẽ nằm dưới nút đang
 * mở gần nhất có level < L. Không cần hiểu nội dung.
 */

export type MarkerKind =
  | 'annex'
  | 'part'
  | 'chapter'
  | 'section'
  | 'article'
  | 'clause'
  | 'point'
  | 'item'

export type Marker = {
  kind: MarkerKind
  level: number
  /** Chuỗi ký hiệu như trong văn bản: "Điều 1.", "1.1", "a)". */
  raw: string
  /** Số/chữ đã bỏ trang trí: "1", "1.1", "a", "ii". null với gạch đầu dòng. */
  number: string | null
  /** Phần còn lại của dòng sau ký hiệu. */
  rest: string
}

export const LEVEL = {
  annex: 0,
  part: 0,
  chapter: 1,
  section: 2,
  article: 3,
  clause: 4,
  point: 10,
  roman: 11,
  item: 12,
} as const

const TRAIL = String.raw`[\s.:\-–—)]*`

// "Phụ lục 01", "PHỤ LỤC A", "Phụ lục:" (không số). Phụ lục đóng mọi nút đang
// mở của hợp đồng chính nên xếp cùng cấp Phần.
const ANNEX_RE = new RegExp(
  String.raw`^(Phụ\s*lục|PHỤ\s*LỤC|Annex|ANNEX|Appendix|APPENDIX)(?:\s+([IVXLC]+|\d{1,2}|[A-Z]))?\b${TRAIL}`,
  'u',
)
const PART_RE = new RegExp(
  String.raw`^(Phần|PHẦN|Part|PART)\s+([IVXLC]+|\d{1,2}|[A-Z])\b${TRAIL}`,
  'u',
)
const CHAPTER_RE = new RegExp(
  String.raw`^(Chương|CHƯƠNG|Chapter|CHAPTER)\s+([IVXLC]+|\d{1,2})\b${TRAIL}`,
  'u',
)
const SECTION_RE = new RegExp(
  String.raw`^(Mục|MỤC)\s+([IVXLC]+|\d{1,2})\b${TRAIL}`,
  'u',
)
const ARTICLE_RE = new RegExp(
  String.raw`^(Điều|ĐIỀU|Article|ARTICLE)\s+(\d{1,3})\b${TRAIL}`,
  'u',
)
const KHOAN_RE = new RegExp(
  String.raw`^(Khoản|KHOẢN)\s+(\d{1,3})\b${TRAIL}`,
  'u',
)
// "1.1", "1.1.1". Mỗi đoạn tối đa 2 chữ số để không nhầm ngày 12.03.2024
// hay số tiền 1.500.000.
const DECIMAL_MULTI_RE = /^(\d{1,2}(?:\.\d{1,2}){1,4})\.?(?:\s+|$)/
// "1." bắt buộc có dấu chấm và khoảng trắng phía sau.
const DECIMAL_SINGLE_RE = /^(\d{1,2})\.(?:\s+|$)/
// "I." "II." đứng đầu dòng, viết hoa: cấp mục lớn kiểu văn bản hành chính.
const ROMAN_UPPER_DOT_RE = /^([IVX]{1,4})\.(?:\s+|$)/
// "A." "B." viết hoa có dấu chấm: mục lớn. "A)" thì là điểm.
const ALPHA_UPPER_DOT_RE = /^([A-Z])\.(?:\s+|$)/
const NUM_PAREN_RE = /^\(?(\d{1,2})\)(?:\s+|$)/
// "(i)", "(ii)", "(iv)": la mã trong ngoặc kép hai bên.
const ROMAN_PAREN_RE = /^\(([ivx]{1,5})\)(?:\s+|$)/
// "ii)", "iii)": la mã chỉ đóng ngoặc, từ 2 chữ trở lên (i) đơn lẻ coi là chữ i).
const ROMAN_CLOSE_RE = /^([ivx]{2,5})\)(?:\s+|$)/
// "a)" "(a)" "đ)" "a." : điểm. Tiếng Việt dùng cả chữ đ.
const ALPHA_RE = /^\(?([a-zđA-ZĐ])[.)](?:\s+|$)/u
const DASH_RE = /^[-–—•·+*▪■●○]\s+/

const LOWER_START_RE = /^\p{Ll}/u

function stripLead(rest: string) {
  return rest.replace(/^[\s.:\-–—)]+/, '').trim()
}

function textual(
  kind: MarkerKind,
  level: number,
  match: RegExpMatchArray,
  text: string,
): Marker | null {
  const rest = stripLead(text.slice(match[0].length))
  // "Điều 3 của Hợp đồng này..." là câu văn, không phải tiêu đề.
  if (rest && LOWER_START_RE.test(rest)) return null
  // "Khoản 2 Điều 5 ..." là tham chiếu chéo, không mở khoản mới.
  if (rest && CROSS_REF_RE.test(rest)) return null
  return {
    kind,
    level,
    raw: match[0].trim(),
    number: match[2] ?? null,
    rest,
  }
}

const CROSS_REF_RE =
  /^(Điều|ĐIỀU|Khoản|KHOẢN|Điểm|ĐIỂM|Chương|CHƯƠNG|Mục|MỤC)\s+\S/u

export function parseMarker(input: string): Marker | null {
  const text = input.trim()
  if (!text) return null

  let match: RegExpMatchArray | null

  if ((match = text.match(ANNEX_RE))) {
    return textual('annex', LEVEL.annex, match, text)
  }
  if ((match = text.match(PART_RE))) {
    return textual('part', LEVEL.part, match, text)
  }
  if ((match = text.match(CHAPTER_RE))) {
    return textual('chapter', LEVEL.chapter, match, text)
  }
  if ((match = text.match(SECTION_RE))) {
    return textual('section', LEVEL.section, match, text)
  }
  if ((match = text.match(ARTICLE_RE))) {
    return textual('article', LEVEL.article, match, text)
  }
  if ((match = text.match(KHOAN_RE))) {
    return textual('clause', LEVEL.clause, match, text)
  }

  if ((match = text.match(DECIMAL_MULTI_RE))) {
    const number = match[1]
    const depth = number.split('.').length
    return {
      kind: 'clause',
      level: LEVEL.clause + depth - 1,
      raw: match[0].trim(),
      number,
      rest: stripLead(text.slice(match[0].length)),
    }
  }
  if ((match = text.match(DECIMAL_SINGLE_RE))) {
    return {
      kind: 'clause',
      level: LEVEL.clause,
      raw: match[0].trim(),
      number: match[1],
      rest: stripLead(text.slice(match[0].length)),
    }
  }

  if ((match = text.match(ROMAN_UPPER_DOT_RE))) {
    const rest = stripLead(text.slice(match[0].length))
    if (!rest || LOWER_START_RE.test(rest)) return null
    return {
      kind: 'chapter',
      level: LEVEL.chapter,
      raw: match[0].trim(),
      number: match[1],
      rest,
    }
  }
  if ((match = text.match(ALPHA_UPPER_DOT_RE))) {
    const rest = stripLead(text.slice(match[0].length))
    if (!rest || LOWER_START_RE.test(rest)) return null
    return {
      kind: 'section',
      level: LEVEL.section,
      raw: match[0].trim(),
      number: match[1],
      rest,
    }
  }

  if ((match = text.match(ROMAN_PAREN_RE))) {
    return {
      kind: 'point',
      level: LEVEL.roman,
      raw: match[0].trim(),
      number: match[1],
      rest: stripLead(text.slice(match[0].length)),
    }
  }
  if ((match = text.match(ROMAN_CLOSE_RE))) {
    return {
      kind: 'point',
      level: LEVEL.roman,
      raw: match[0].trim(),
      number: match[1],
      rest: stripLead(text.slice(match[0].length)),
    }
  }
  if ((match = text.match(NUM_PAREN_RE))) {
    return {
      kind: 'point',
      level: LEVEL.point,
      raw: match[0].trim(),
      number: match[1],
      rest: stripLead(text.slice(match[0].length)),
    }
  }
  if ((match = text.match(ALPHA_RE))) {
    return {
      kind: 'point',
      level: LEVEL.point,
      raw: match[0].trim(),
      number: match[1].toLowerCase(),
      rest: stripLead(text.slice(match[0].length)),
    }
  }
  if ((match = text.match(DASH_RE))) {
    return {
      kind: 'item',
      level: LEVEL.item,
      raw: match[0].trim(),
      number: null,
      rest: text.slice(match[0].length).trim(),
    }
  }
  return null
}

/** Các loại ký hiệu có tiêu đề riêng (Điều 1. ĐỐI TƯỢNG HỢP ĐỒNG). */
export function isHeadingKind(kind: MarkerKind) {
  return (
    kind === 'annex' ||
    kind === 'part' ||
    kind === 'chapter' ||
    kind === 'section' ||
    kind === 'article'
  )
}
