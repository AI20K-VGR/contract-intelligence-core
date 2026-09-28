import { getJson } from '../api/client'
import {
  decodeJwtPayload,
  realmRolesFromToken,
  tenantIdFromToken,
} from './oidc'
import {
  backendRoleFromRealmRoles,
  parseBackendRole,
  toAppRole,
  type SessionUser,
} from './session'

type MeResponse = {
  id: string
  email: string
  display_name: string
  role: string
  tenant_id: string
}

function sessionFromJwt(accessToken: string): SessionUser {
  const payload = decodeJwtPayload(accessToken)
  if (!payload) {
    throw new Error('Access token Keycloak không hợp lệ.')
  }

  const email =
    (typeof payload.email === 'string' && payload.email) ||
    (typeof payload.preferred_username === 'string' &&
      payload.preferred_username) ||
    ''
  const name =
    (typeof payload.name === 'string' && payload.name) ||
    (typeof payload.given_name === 'string' && payload.given_name) ||
    email
  const id = typeof payload.sub === 'string' ? payload.sub : email
  const backendRole = backendRoleFromRealmRoles(
    realmRolesFromToken(accessToken),
  )

  return {
    id,
    email,
    name,
    tenantId: tenantIdFromToken(accessToken) ?? '',
    backendRole,
    role: toAppRole(backendRole),
  }
}

function sessionFromMe(me: MeResponse, accessToken: string): SessionUser {
  const backendRole =
    parseBackendRole(me.role) ??
    backendRoleFromRealmRoles(realmRolesFromToken(accessToken))

  return {
    id: me.id,
    email: me.email,
    name: me.display_name,
    tenantId: me.tenant_id,
    backendRole,
    role: toAppRole(backendRole),
  }
}

export async function buildSessionUser(
  accessToken: string,
): Promise<SessionUser> {
  try {
    const me = await getJson<MeResponse>('/api/v1/auth/me', {
      accessToken,
      signal: AbortSignal.timeout(4000),
    })
    return sessionFromMe(me, accessToken)
  } catch {
    // Backend CI chưa chạy (cổng 8000 đang là app khác) — dùng claim JWT.
    return sessionFromJwt(accessToken)
  }
}
