export type SplitRole = 'contract' | 'annex'

/** Mỗi phần chỉ giữ trang cuối và vai trò; trang đầu suy ra từ phần trước. */
export type DraftPart = {
  key: string
  end: number
  role: SplitRole
}

export type ResolvedPart = {
  key: string
  pageStart: number
  pageEnd: number
  role: SplitRole
}

let counter = 0
function nextKey() {
  counter += 1
  return `part-${counter}`
}

/** Mặc định: cả file là một hợp đồng. Người dùng chia nhỏ tiếp. */
export function initialParts(pageCount: number): DraftPart[] {
  return [{ key: nextKey(), end: Math.max(pageCount, 1), role: 'contract' }]
}

/** Trang cuối của phần cuối luôn là trang cuối file, nên các phần phủ đủ 1..N. */
export function resolveParts(
  parts: DraftPart[],
  pageCount: number,
): ResolvedPart[] {
  let start = 1
  return parts.map((part, index) => {
    const last = index === parts.length - 1
    const end = last ? pageCount : part.end
    const resolved = {
      key: part.key,
      pageStart: start,
      pageEnd: end,
      role: part.role,
    }
    start = end + 1
    return resolved
  })
}

/** Thêm một phần mới ở cuối, lấy nửa sau của phần cuối hiện tại. */
export function addPart(parts: DraftPart[], pageCount: number): DraftPart[] {
  const resolved = resolveParts(parts, pageCount)
  const last = resolved[resolved.length - 1]
  if (!last || last.pageEnd <= last.pageStart) return parts
  const cut = last.pageStart + Math.floor((last.pageEnd - last.pageStart) / 2)
  const head = parts.slice(0, -1)
  return [
    ...head,
    { key: parts[parts.length - 1].key, end: cut, role: last.role },
    { key: nextKey(), end: pageCount, role: 'annex' },
  ]
}

export function removePart(parts: DraftPart[], key: string): DraftPart[] {
  if (parts.length <= 1) return parts
  return parts.filter((part) => part.key !== key)
}

/** Trả về lỗi đầu tiên theo thứ tự người dùng gặp, hoặc null nếu hợp lệ. */
export function validateParts(
  parts: DraftPart[],
  pageCount: number,
): string | null {
  if (pageCount < 1) return 'Chưa biết số trang của file.'
  const resolved = resolveParts(parts, pageCount)
  for (const part of resolved) {
    if (!Number.isInteger(part.pageEnd) || part.pageEnd < part.pageStart) {
      return `Phần bắt đầu ở trang ${part.pageStart} phải kết thúc từ trang ${part.pageStart} trở đi.`
    }
    if (part.pageEnd > pageCount) {
      return `File chỉ có ${pageCount} trang.`
    }
  }
  const contracts = resolved.filter((part) => part.role === 'contract').length
  if (contracts !== 1) {
    return contracts === 0
      ? 'Cần đúng một phần là hợp đồng chính, hiện chưa có.'
      : `Cần đúng một phần là hợp đồng chính, hiện có ${contracts}.`
  }
  return null
}

export function toRequestParts(parts: DraftPart[], pageCount: number) {
  return resolveParts(parts, pageCount).map((part) => ({
    page_start: part.pageStart,
    page_end: part.pageEnd,
    role: part.role,
  }))
}
