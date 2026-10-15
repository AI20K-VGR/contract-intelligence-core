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

export type ShareRole = 'OPERATOR' | 'REVIEWER' | 'ADMINISTRATOR'

export const shareRoleLabels: Record<ShareRole, string> = {
  OPERATOR: 'Vận hành',
  REVIEWER: 'Thẩm định',
  ADMINISTRATOR: 'Quản trị',
}

/*
 * Backend cần cả vai trò lẫn quyền chia sẻ (shared/acl.py): quyền "Được sửa"
 * không cho Vận hành thẩm định, cũng không cho Thẩm định sửa hồ sơ hay duyệt.
 */
const GRANT_EFFECT: Record<ShareRole, Record<SharePermission, string>> = {
  OPERATOR: {
    read: 'Xem hồ sơ, kết quả và trích dẫn. Không sửa được.',
    edit: 'Xem, sửa hồ sơ và chạy lại phân tích. Không thẩm định được.',
  },
  REVIEWER: {
    read: 'Xem hồ sơ và kết quả thẩm định. Không thẩm định được.',
    edit: 'Xem và thẩm định trích dẫn, xung đột. Không sửa hồ sơ, không duyệt.',
  },
  ADMINISTRATOR: {
    read: 'Xem hồ sơ. Không sửa, không thẩm định được.',
    edit: 'Xem, sửa, thẩm định và duyệt hồ sơ.',
  },
}

/** Người này làm được gì trên hồ sơ, theo vai trò và quyền chia sẻ. */
export function grantEffect(
  role: ShareRole | undefined,
  permission: SharePermission,
) {
  if (!role) {
    return permission === 'read'
      ? 'Chỉ xem hồ sơ.'
      : 'Thao tác theo vai trò của người nhận.'
  }
  return GRANT_EFFECT[role][permission]
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
