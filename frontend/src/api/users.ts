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
    if (error.code === 'invite_not_applicable') {
      return 'Chỉ gửi lại email khi người dùng còn ở trạng thái đã mời.'
    }
    if (error.code === 'email_not_configured') {
      return 'Hệ thống chưa cấu hình email mời. Phía backend cần bật SMTP trên Keycloak.'
    }
    if (error.code === 'keycloak_unavailable') {
      return 'Không kết nối được dịch vụ đăng nhập. Thử lại sau.'
    }
    if (error.status === 403) {
      return 'Chỉ quản trị viên mới quản lý được người dùng.'
    }
    if (error.status === 404 && error.message === 'Not Found') {
      return 'API quản lý người dùng chưa có trên backend.'
    }
    if (error.status === 404) {
      return 'Không tìm thấy người dùng này.'
    }
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được backend. API quản lý người dùng chưa sẵn sàng.'
  }
  return 'Không thực hiện được. Thử lại.'
}
