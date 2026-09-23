import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { AuthContext } from './context'
import {
  getUserManager,
  isKeycloakConfigured,
  requireUserManager,
} from './oidc'
import { buildSessionUser } from './profile'
import type { SessionUser } from './session'

function isAuthCallbackPath(pathname: string) {
  return pathname === '/auth/callback' || pathname === '/auth/silent-callback'
}

let ssoCallbackTask: Promise<SessionUser> | null = null

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [ready, setReady] = useState(false)
  const configured = isKeycloakConfigured()

  useEffect(() => {
    if (isAuthCallbackPath(window.location.pathname)) {
      setReady(true)
      return
    }

    const manager = getUserManager()
    let cancelled = false

    async function hydrate() {
      try {
        const oidcUser = await manager?.getUser()
        if (!oidcUser?.access_token || oidcUser.expired) {
          if (!cancelled) {
            setUser(null)
          }
          return
        }
        const session = await buildSessionUser(oidcUser.access_token)
        if (!cancelled) {
          setUser(session)
        }
      } catch {
        if (!cancelled) {
          setUser(null)
        }
      } finally {
        if (!cancelled) {
          setReady(true)
        }
      }
    }

    void hydrate()

    const onSignedOut = () => {
      setUser(null)
    }

    const onTokenExpired = () => {
      void (async () => {
        try {
          const renewed = await manager?.signinSilent()
          if (renewed?.access_token) {
            const session = await buildSessionUser(renewed.access_token)
            if (!cancelled) {
              setUser(session)
            }
            return
          }
        } catch {
          // Keycloak session hết hạn — về màn login
        }
        if (!cancelled) {
          setUser(null)
        }
      })()
    }

    manager?.events.addUserSignedOut(onSignedOut)
    manager?.events.addAccessTokenExpired(onTokenExpired)

    return () => {
      cancelled = true
      manager?.events.removeUserSignedOut(onSignedOut)
      manager?.events.removeAccessTokenExpired(onTokenExpired)
    }
  }, [])

  const loginWithSso = useCallback(async (email: string) => {
    ssoCallbackTask = null
    const manager = requireUserManager()
    await manager.signinRedirect({
      extraQueryParams: { login_hint: email },
    })
  }, [])

  const completeSsoCallback = useCallback(() => {
    if (!ssoCallbackTask) {
      ssoCallbackTask = (async () => {
        const manager = requireUserManager()
        const params = new URLSearchParams(window.location.search)
        if (!params.get('code')) {
          throw new Error(
            'Keycloak không trả authorization code. Đăng nhập lại từ đầu.',
          )
        }
        let oidcUser = null
        try {
          oidcUser = await manager.signinRedirectCallback()
        } catch (cause) {
          const existing = await manager.getUser()
          if (existing?.access_token && !existing.expired) {
            oidcUser = existing
          } else {
            throw cause
          }
        }
        if (!oidcUser?.access_token) {
          throw new Error('Không nhận được access token từ Keycloak.')
        }
        const session = await buildSessionUser(oidcUser.access_token)
        setUser(session)
        return session
      })().catch((cause: unknown) => {
        ssoCallbackTask = null
        throw cause
      })
    }
    return ssoCallbackTask
  }, [])

  const logout = useCallback(async () => {
    setUser(null)
    const manager = getUserManager()
    if (!manager) {
      return
    }
    try {
      await manager.signoutRedirect()
    } catch {
      await manager.removeUser()
    }
  }, [])

  const value = useMemo(
    () => ({
      user,
      ready,
      configured,
      loginWithSso,
      completeSsoCallback,
      logout,
    }),
    [completeSsoCallback, configured, loginWithSso, logout, ready, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
