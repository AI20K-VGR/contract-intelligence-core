import type { DossierUploadInput } from '../api/dossierUpload'

/**
 * Hồ sơ đã điền ở trang Tải lên, chờ chọn hợp đồng và phụ lục trong file trộn.
 * Chưa gửi gì lên máy chủ; chỉ sống trong tab này (tệp không vào được URL).
 */
const drafts = new Map<string, DossierUploadInput>()

export function stashSplitDraft(input: DossierUploadInput) {
  // Chỉ giữ một bản nháp: tệp có thể tới vài trăm MB.
  drafts.clear()
  const id = crypto.randomUUID()
  drafts.set(id, input)
  return id
}

export function getSplitDraft(id: string | null | undefined) {
  return id ? (drafts.get(id) ?? null) : null
}

export function dropSplitDraft(id: string | null | undefined) {
  if (id) drafts.delete(id)
}
