export type SharePermission = 'read' | 'edit'

export type ShareGrantLike = {
  permission?: SharePermission
  expires_at?: string | null
  status?: string
}

export const permissionLabels: Record<SharePermission, string> = {
  read: 'Chỉ xem',
  edit: 'Được sửa',
}

/** Chưa có trường permission nghĩa là bản chia sẻ cũ, backend coi là được sửa. */
export function grantPermission(grant: ShareGrantLike): SharePermission {
  return grant.permission === 'read' ? 'read' : 'edit'
}

export function isGrantExpired(grant: ShareGrantLike, now = Date.now()) {
  if (!grant.expires_at) return false
  const time = new Date(grant.expires_at).getTime()
  return Number.isNaN(time) || time <= now
}

export function formatExpiry(value: string | null | undefined) {
  if (!value) return 'Không hết hạn'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Không hết hạn'
    : date.toLocaleDateString('vi-VN')
}

/** yyyy-mm-dd theo giờ máy, dùng cho ô chọn ngày. */
export function toDateInput(value: string | null | undefined) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** Hết hạn vào cuối ngày đã chọn (giờ máy). Để trống là không hết hạn. */
export function fromDateInput(value: string): string | null {
  if (!value) return null
  const date = new Date(`${value}T23:59:59`)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

export function todayInput() {
  return toDateInput(new Date().toISOString())
}
