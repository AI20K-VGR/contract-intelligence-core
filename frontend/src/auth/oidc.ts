import { UserManager, WebStorageStateStore, type User } from 'oidc-client-ts'

export type KeycloakConfig = {
  url: string
  realm: string
  clientId: string
}

export function getKeycloakConfig(): KeycloakConfig | null {
  const url = import.meta.env.VITE_KEYCLOAK_URL?.replace(/\/$/, '')
  const realm = import.meta.env.VITE_KEYCLOAK_REALM?.trim()
  const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID?.trim()
  if (!url || !realm || !clientId) {
    return null
  }
  return { url, realm, clientId }
}

export function isKeycloakConfigured(): boolean {
  return getKeycloakConfig() !== null
}

let manager: UserManager | null | undefined

export function getUserManager(): UserManager | null {
  if (manager !== undefined) {
    return manager
  }

  const config = getKeycloakConfig()
  if (!config || typeof window === 'undefined') {
    manager = null
    return null
  }

  const origin = window.location.origin
  // localtunnel shows an IP gate to the browser. Dev server proxies /keycloak
  // and adds the bypass header, so the SPA never calls loca.lt directly.
  const keycloakBase = config.url.includes('loca.lt')
    ? `${origin}/keycloak`
    : config.url
  const authority = `${keycloakBase}/realms/${config.realm}`
  manager = new UserManager({
    authority,
    client_id: config.clientId,
    redirect_uri: `${origin}/auth/callback`,
    silent_redirect_uri: `${origin}/auth/silent-callback`,
    post_logout_redirect_uri: `${origin}/`,
    response_type: 'code',
    scope: 'openid profile email',
    disablePKCE: false,
    automaticSilentRenew: true,
    includeIdTokenInSilentRenew: true,
    monitorSession: false,
    filterProtocolClaims: true,
    loadUserInfo: false,
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  })

  return manager
}

export function requireUserManager(): UserManager {
  const instance = getUserManager()
  if (!instance) {
    throw new Error(
      'Chưa cấu hình Keycloak. Thêm VITE_KEYCLOAK_URL, VITE_KEYCLOAK_REALM, VITE_KEYCLOAK_CLIENT_ID vào .env.local.',
    )
  }
  return instance
}

export async function getAccessToken(): Promise<string | null> {
  const instance = getUserManager()
  if (!instance) {
    return null
  }

  let user: User | null = await instance.getUser()
  if (user && !user.expired && user.access_token) {
    return user.access_token
  }

  try {
    user = await instance.signinSilent()
    return user?.access_token ?? null
  } catch {
    return null
  }
}

export function decodeJwtPayload(
  token: string,
): Record<string, unknown> | null {
  const segment = token.split('.')[1]
  if (!segment) {
    return null
  }

  try {
    const padded = segment.replace(/-/g, '+').replace(/_/g, '/')
    const padLength = (4 - (padded.length % 4)) % 4
    const base64 = padded + '='.repeat(padLength)
    const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0))
    return JSON.parse(new TextDecoder().decode(bytes)) as Record<
      string,
      unknown
    >
  } catch {
    return null
  }
}

export function tenantIdFromToken(token: string): string | null {
  const payload = decodeJwtPayload(token)
  const tenantId = payload?.tenant_id
  return typeof tenantId === 'string' && tenantId.length > 0 ? tenantId : null
}

export function realmRolesFromToken(token: string): string[] {
  const payload = decodeJwtPayload(token)
  const realmAccess = payload?.realm_access
  if (!realmAccess || typeof realmAccess !== 'object') {
    return []
  }
  const roles = (realmAccess as { roles?: unknown }).roles
  if (!Array.isArray(roles)) {
    return []
  }
  return roles.filter((role): role is string => typeof role === 'string')
}
