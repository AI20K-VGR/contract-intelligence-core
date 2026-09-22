export type AppRole = 'admin' | 'user'

export type UserRole = 'OPERATOR' | 'REVIEWER' | 'ADMINISTRATOR'

export type SessionUser = {
  id: string
  role: AppRole
  backendRole: UserRole
  name: string
  email: string
  tenantId: string
}

export function homePath(role: AppRole) {
  return role === 'admin' ? '/tong-quan' : '/ho-so-cua-toi'
}

export function dossiersPath(role: AppRole) {
  return role === 'admin' ? '/ho-so' : '/ho-so-cua-toi'
}

export function dossiersLabel(role: AppRole) {
  return role === 'admin' ? 'Hồ sơ' : 'Hồ sơ của tôi'
}

export function toAppRole(backendRole: UserRole): AppRole {
  return backendRole === 'ADMINISTRATOR' ? 'admin' : 'user'
}

export function parseBackendRole(value: string | undefined): UserRole | null {
  if (
    value === 'ADMINISTRATOR' ||
    value === 'REVIEWER' ||
    value === 'OPERATOR'
  ) {
    return value
  }
  return null
}

export function backendRoleFromRealmRoles(roles: string[]): UserRole {
  if (roles.includes('ADMINISTRATOR') || roles.includes('ci_administrator')) {
    return 'ADMINISTRATOR'
  }
  if (roles.includes('REVIEWER') || roles.includes('ci_reviewer')) {
    return 'REVIEWER'
  }
  if (roles.includes('OPERATOR') || roles.includes('ci_operator')) {
    return 'OPERATOR'
  }
  return 'OPERATOR'
}

export function validateWorkEmail(raw: string): string {
  const email = raw.trim().toLowerCase()
  if (!email) {
    throw new Error('Nhập email doanh nghiệp để tiếp tục.')
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new Error('Email không đúng định dạng.')
  }
  return email
}
