import { useEffect, useState } from 'react'
import { getDossierStructure } from '../api/structure'
import type { SessionUser, UserRole } from './session'
import { useAuth } from './useAuth'

/*
 * Bản sao phía trình duyệt của backend/shared/acl.py để ẩn sẵn nút sẽ bị 403.
 * Backend vẫn là nơi quyết định; ở đây chỉ để giao diện không mời bấm nhầm.
 *
 * Cần cả hai: vai trò cho phép loại việc, và hồ sơ cho phép người này
 * (chủ hồ sơ, hoặc grant còn hạn; việc thay đổi cần grant "edit").
 */

type Grant = {
  id?: unknown
  email?: unknown
  permission?: unknown
  expires_at?: unknown
  status?: unknown
}

export type DossierPermissions = {
  /** Đã đọc metadata hồ sơ; trước đó chỉ dựa vào vai trò. */
  known: boolean
  owner: boolean
  /** Quyền chia sẻ còn hiệu lực của người này; null nếu là chủ hoặc không có. */
  grant: 'read' | 'edit' | null
  expired: boolean
  /** Sửa hồ sơ, xác nhận manifest, tách file, chạy lại, hủy (DOSSIER_EDIT). */
  canEdit: boolean
  /** Lưu thẩm định, khóa hồ sơ, OCR lại trang khi là Thẩm định (REVIEW_MUTATE). */
  canReview: boolean
  /** Xem hàng đợi thẩm định (REVIEW_READ). */
  canSeeReview: boolean
  /** Xóa hồ sơ, đổi chia sẻ (DOSSIER_MANAGE). */
  canManage: boolean
  /** Phê duyệt (APPROVE). */
  canApprove: boolean
  /** Câu giải thích khi không được sửa hoặc không được thẩm định. */
  editBlocked: string | null
  reviewBlocked: string | null
}

const EDIT_ROLES: UserRole[] = ['OPERATOR', 'ADMINISTRATOR']
const REVIEW_ROLES: UserRole[] = ['REVIEWER', 'ADMINISTRATOR']

function grantFor(
  metadata: Record<string, unknown> | null,
  user: Pick<SessionUser, 'id' | 'email'>,
): Grant | null {
  if (metadata?.access_scope === 'mine') return null
  const list = metadata?.shared_with
  if (!Array.isArray(list)) return null
  const email = user.email.trim().toLowerCase()
  return (
    (list as Grant[]).find(
      (grant) =>
        grant &&
        typeof grant === 'object' &&
        (grant.id === user.id ||
          (email !== '' &&
            String(grant.email ?? '')
              .trim()
              .toLowerCase() === email)),
    ) ?? null
  )
}

function grantLive(grant: Grant, now: number) {
  if (grant.status === 'disabled') return false
  if (grant.expires_at == null || grant.expires_at === '') return true
  const time = new Date(String(grant.expires_at)).getTime()
  return Number.isFinite(time) && now < time
}

export function dossierPermissions(
  user: Pick<SessionUser, 'id' | 'email' | 'backendRole'> | null | undefined,
  metadata: Record<string, unknown> | null | undefined,
  now = Date.now(),
): DossierPermissions {
  const role = user?.backendRole
  const roleEdit = Boolean(role && EDIT_ROLES.includes(role))
  const roleReview = Boolean(role && REVIEW_ROLES.includes(role))
  const roleApprove = role === 'ADMINISTRATOR'
  const roleEditMsg = 'Vai trò Thẩm định không sửa hay chạy lại hồ sơ.'
  const roleReviewMsg = 'Chỉ Thẩm định hoặc Quản trị được thẩm định.'

  if (!user || metadata === undefined) {
    return {
      known: false,
      owner: false,
      grant: null,
      expired: false,
      canEdit: roleEdit,
      canReview: roleReview,
      canSeeReview: roleReview,
      canManage: roleEdit,
      canApprove: roleApprove,
      editBlocked: roleEdit ? null : roleEditMsg,
      reviewBlocked: roleReview ? null : roleReviewMsg,
    }
  }

  const owner =
    typeof metadata?.created_by === 'string' &&
    metadata.created_by !== '' &&
    metadata.created_by === user.id
  const found = owner ? null : grantFor(metadata ?? null, user)
  const live = found ? grantLive(found, now) : false
  const grant =
    found && live ? (found.permission === 'read' ? 'read' : 'edit') : null
  const expired = Boolean(found && !live)
  const reads = owner || grant !== null
  const changes = owner || grant === 'edit'

  const docMsg = expired
    ? 'Quyền chia sẻ hồ sơ này đã hết hạn. Liên hệ người chia sẻ để gia hạn.'
    : grant === 'read'
      ? 'Bạn chỉ có quyền xem hồ sơ này. Liên hệ người chia sẻ để được sửa.'
      : 'Bạn không có quyền trên hồ sơ này.'

  return {
    known: true,
    owner,
    grant,
    expired,
    canEdit: roleEdit && changes,
    canReview: roleReview && changes,
    canSeeReview: roleReview && reads,
    canManage: (roleEdit && owner) || role === 'ADMINISTRATOR',
    canApprove: roleApprove && changes,
    editBlocked: !roleEdit ? roleEditMsg : changes ? null : docMsg,
    reviewBlocked: !roleReview ? roleReviewMsg : changes ? null : docMsg,
  }
}

const cache = new Map<string, Promise<Record<string, unknown> | null>>()

/** Quyền của người đang đăng nhập trên một hồ sơ; đọc metadata một lần cho mỗi hồ sơ. */
export function useDossierPermissions(dossierId: string | null | undefined) {
  const { user } = useAuth()
  const [metadata, setMetadata] = useState<
    Record<string, unknown> | null | undefined
  >(undefined)

  useEffect(() => {
    setMetadata(undefined)
    if (!dossierId) return
    let active = true
    let request = cache.get(dossierId)
    if (!request) {
      request = getDossierStructure(dossierId).then((row) => row.metadata)
      cache.set(dossierId, request)
      // Quyền có thể đổi (chia sẻ, hết hạn): chỉ giữ trong lúc chuyển trang.
      window.setTimeout(() => cache.delete(dossierId), 30_000)
    }
    request
      .then((value) => {
        if (active) setMetadata(value)
      })
      .catch(() => {
        cache.delete(dossierId)
      })
    return () => {
      active = false
    }
  }, [dossierId])

  return dossierPermissions(user, metadata)
}
