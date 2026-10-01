import type { Dossier } from '../data/dossiers'
import { formatExpiry, permissionLabels } from '../data/shareGrant'
import { MaterialIcon } from './icons'

/** Quyền người đang đăng nhập có trên hồ sơ được chia sẻ: chỉ xem hoặc sửa, và hạn. */
export function ShareGrantBadge({ grant }: { grant: Dossier['myGrant'] }) {
  if (!grant) return null
  if (grant.expired) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-error-container px-2 py-0.5 font-label-sm text-label-sm text-on-error-container">
        <MaterialIcon name="event_busy" className="text-[14px]" />
        Đã hết hạn, không mở được
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded bg-surface-container px-2 py-0.5 font-label-sm text-label-sm text-on-surface">
      <MaterialIcon
        name={grant.permission === 'read' ? 'visibility' : 'edit'}
        className="text-[14px]"
      />
      {permissionLabels[grant.permission]} · {formatExpiry(grant.expires_at)}
    </span>
  )
}
