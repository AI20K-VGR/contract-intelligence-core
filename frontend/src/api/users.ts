import { ApiError, requestJson } from './client'

export type ManagedUserRole = 'OPERATOR' | 'REVIEWER' | 'ADMINISTRATOR'

export type ManagedUserStatus = 'invited' | 'active' | 'disabled'

export type ManagedUser = {
  id: string
  email: string
  display_name: string
  role: ManagedUserRole
  status: ManagedUserStatus
  created_at: string
  invited_at?: string | null
  last_login_at?: string | null
}

export type UserListQuery = {
  q?: string
  role?: ManagedUserRole
  status?: ManagedUserStatus
  limit: number
  offset: number
  signal?: AbortSignal
}

export type CreateUserInput = {
  email: string
  display_name: string
  role: ManagedUserRole
}

const USERS_PATH = '/api/v1/users'

function usersQuery(query: UserListQuery) {
  const params = new URLSearchParams()
  if (query.q) params.set('q', query.q)
  if (query.role) params.set('role', query.role)
  if (query.status) params.set('status', query.status)
  params.set('limit', String(query.limit))
  params.set('offset', String(query.offset))
  return `${USERS_PATH}?${params.toString()}`
}

export async function listUsers(query: UserListQuery) {
  const { data, meta } = await requestJson<ManagedUser[]>(usersQuery(query), {
    signal: query.signal,
  })
  return {
    users: data,
    total: meta?.total ?? data.length,
  }
}

/** Một thành viên đang hoạt động cùng tenant (GET /users/lookup, DOC-05b v4.0.0). */
export type TenantUser = {
  id: string
  email: string
  display_name: string
  role: ManagedUserRole
}

/**
 * Thành viên đang bật cùng tenant để chọn người nhận (GET /users/directory).
 * Khác GET /users: không có người bị khoá hay thiếu tenant_id trong Keycloak,
 * đúng tập người PUT /dossiers/{id}/access chấp nhận.
 */
export async function listUserDirectory(query: {
  limit: number
  offset: number
  signal?: AbortSignal
}) {
  const params = new URLSearchParams({
    limit: String(query.limit),
    offset: String(query.offset),
  })
  const { data } = await requestJson<TenantUser[]>(
    `${USERS_PATH}/directory?${params.toString()}`,
    { signal: query.signal },
  )
  return data
}

/**
 * Tra đúng một email trong đơn vị (GET /users/lookup), để chia sẻ hồ sơ mà
 * không cần xem cả danh sách người dùng. Chỉ có người đã kích hoạt tài khoản.
 * null khi không có ai (404 user_not_found: khác đơn vị, bị khoá, chưa kích
 * hoạt hay không tồn tại đều trả cùng một câu).
 */
export async function lookupUserByEmail(email: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ email: email.trim() })
  try {
    const { data } = await requestJson<TenantUser>(
      `${USERS_PATH}/lookup?${params.toString()}`,
      { signal },
    )
    return data
  } catch (cause) {
    if (cause instanceof ApiError && cause.code === 'user_not_found')
      return null
    throw cause
  }
}

export async function createUser(input: CreateUserInput) {
  const { data } = await requestJson<ManagedUser>(USERS_PATH, {
    method: 'POST',
    json: input,
  })
  return data
}

export async function updateUserRole(id: string, role: ManagedUserRole) {
  const { data } = await requestJson<ManagedUser>(
    `${USERS_PATH}/${encodeURIComponent(id)}`,
    { method: 'PATCH', json: { role } },
  )
  return data
}

export async function setUserEnabled(id: string, enabled: boolean) {
  const action = enabled ? 'enable' : 'disable'
  const { data } = await requestJson<ManagedUser>(
    `${USERS_PATH}/${encodeURIComponent(id)}/${action}`,
    { method: 'POST' },
  )
  return data
}

export async function resendUserInvite(id: string) {
  const { data } = await requestJson<ManagedUser>(
    `${USERS_PATH}/${encodeURIComponent(id)}/invite`,
    { method: 'POST' },
  )
  return data
}

export function userAdminErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return null
  }
  if (error instanceof ApiError) {
    if (error.code === 'email_exists') {
      return 'Email này đã có trong hệ thống.'
    }
    if (error.code === 'last_administrator') {
      return 'Cần giữ ít nhất một quản trị viên.'
    }
    if (error.code === 'cannot_disable_self') {
      return 'Không khóa được tài khoản đang đăng nhập.'
    }
    if (error.code === 'cannot_change_own_role') {
      return 'Không đổi được vai trò của tài khoản đang đăng nhập.'
    }
    // Backend trả invalid_invite_state (409); invite_not_applicable là tên cũ.
    if (
      error.code === 'invalid_invite_state' ||
      error.code === 'invite_not_applicable'
    ) {
      return 'Người này đã đặt mật khẩu và kích hoạt tài khoản nên không cần gửi lại lời mời. Danh sách đã được cập nhật.'
    }
    if (error.code === 'keycloak_forbidden') {
      return 'Dịch vụ đăng nhập từ chối thao tác này. Vui lòng báo quản trị viên.'
    }
    if (error.code === 'keycloak_error') {
      return 'Dịch vụ đăng nhập gặp lỗi nên chưa thực hiện được. Thử lại sau.'
    }
    if (error.code === 'email_domain_undeliverable') {
      return 'Tên miền email không nhận được thư, vui lòng kiểm tra lại.'
    }
    if (error.code === 'email_not_configured') {
      return 'Hệ thống chưa gửi được email mời. Vui lòng báo quản trị viên.'
    }
    if (error.code === 'keycloak_unavailable') {
      return 'Không kết nối được dịch vụ đăng nhập. Thử lại sau.'
    }
    if (error.status === 403) {
      return 'Chỉ quản trị viên mới quản lý được người dùng.'
    }
    if (error.status === 404 && error.message === 'Not Found') {
      return 'Chức năng quản lý người dùng chưa sẵn sàng. Vui lòng báo quản trị viên.'
    }
    if (error.status === 404) {
      return 'Không tìm thấy người dùng này.'
    }
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được máy chủ nên chưa tải được người dùng. Vui lòng thử lại.'
  }
  return 'Không thực hiện được. Thử lại.'
}
