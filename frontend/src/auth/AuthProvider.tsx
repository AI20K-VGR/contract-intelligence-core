import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { openAuthChannel, type AuthChannel } from './authChannel'
import { AuthContext } from './context'
import {
  FIRST_SESSION_TIMEOUT_SECONDS,
  getUserManager,
  isKeycloakConfigured,
  renewSession,
  requireUserManager,
} from './oidc'
import { buildSessionUser } from './profile'
import { isSessionEnded } from './sessionEnded'
import { SessionExpiredDialog } from './SessionExpiredDialog'
import { homePath, type SessionUser } from './session'

function isAuthCallbackPath(pathname: string) {
  return pathname === '/auth/callback' || pathname === '/auth/silent-callback'
}

let ssoCallbackTask: Promise<SessionUser> | null = null

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [ready, setReady] = useState(false)
  const configured = isKeycloakConfigured()
  // Kênh lexis-auth: báo các tab khác khi đăng nhập / đăng xuất (#130).
  const channel = useRef<AuthChannel | null>(null)
  // Người dùng hiện tại, để biết tab khác vừa đăng nhập bằng tài khoản khác.
  const currentUser = useRef<SessionUser | null>(null)
  useEffect(() => {
    currentUser.current = user
  }, [user])

  useEffect(() => {
    const manager = getUserManager()
    let cancelled = false

    async function hydrate() {
      try {
        let oidcUser = await manager?.getUser()
        if (!oidcUser?.access_token || oidcUser.expired) {
          // Phiên chỉ ở bộ nhớ tab: F5 hay tab mới lấy lại bằng iframe.
          // ready vẫn false tới khi xong, nên route bảo vệ không nháy sang đăng nhập.
          try {
            // Chờ ngắn hơn gia hạn nền: iframe không trả lời thì hiện form
            // đăng nhập sau 10 giây, không để trang trắng 30 giây.
            oidcUser = manager
              ? await renewSession(manager, {
                  timeoutSeconds: FIRST_SESSION_TIMEOUT_SECONDS,
                })
              : null
          } catch {
            oidcUser = null
          }
        }
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

    // Trang callback tự hoàn tất đăng nhập (completeSsoCallback).
    if (isAuthCallbackPath(window.location.pathname)) setReady(true)
    else void hydrate()

    const onSignedOut = () => {
      setUser(null)
    }

    // Gần hết hạn: gia hạn trước bằng iframe. Lỗi thì để onTokenExpired xử lý.
    const onTokenExpiring = () => {
      if (!manager) return
      renewSession(manager)
        .then(async (renewed) => {
          if (!renewed?.access_token) return
          const session = await buildSessionUser(renewed.access_token)
          if (!cancelled) setUser(session)
        })
        .catch(() => {})
    }

    const onTokenExpired = () => {
      void (async () => {
        try {
          const renewed = manager ? await renewSession(manager) : null
          if (renewed?.access_token) {
            const session = await buildSessionUser(renewed.access_token)
            if (!cancelled) {
              setUser(session)
            }
            return
          }
        } catch (cause) {
          // Gia hạn chỉ chậm hoặc lỗi mạng: phiên Keycloak có thể vẫn còn.
          // Giữ người dùng; thử lại khi tab hiện lại hoặc khi gọi API
          // (getAccessToken). Chỉ phiên đã hết mới về màn đăng nhập.
          if (!isSessionEnded(cause)) return
        }
        if (!cancelled) {
          setUser(null)
        }
      })()
    }

    // Tab chạy nền có thể lỡ mốc gia hạn: hiện lại mà token đã hết thì gia hạn ngay.
    const onVisible = () => {
      if (document.visibilityState !== 'visible' || !manager) return
      void manager.getUser().then((current) => {
        if (current?.expired) onTokenExpired()
      })
    }

    // Tab khác vừa đăng nhập: luôn hỏi lại Keycloak (cookie SSO mới), kể cả
    // khi tab này còn token. Người khác (sub khác) thì đổi người dùng và về
    // trang chủ của vai trò mới, để không thao tác dưới danh tính cũ.
    const onOtherTabLogin = async () => {
      if (!manager) return
      try {
        // Bỏ phiên cũ trước: oidc-client-ts từ chối (login_required) phiên mới
        // có sub khác phiên đang giữ (validateSubOnSilentRenew), mà ở đây đổi
        // người là chuyện có thể xảy ra. Ta tự so sub ngay bên dưới.
        await manager.removeUser()
        const renewed = await renewSession(manager, { force: true })
        if (!renewed?.access_token || cancelled) return
        const session = await buildSessionUser(renewed.access_token)
        if (cancelled) return
        const previous = currentUser.current
        setUser(session)
        if (previous && previous.id !== session.id) {
          window.location.assign(homePath(session.role))
        }
      } catch (cause) {
        if (isSessionEnded(cause) && !cancelled) setUser(null)
      }
    }

    // Tab khác đăng xuất: bỏ phiên trong bộ nhớ tab này.
    const authChannel = openAuthChannel((message) => {
      if (message === 'logout') {
        void manager?.removeUser()
        if (!cancelled) setUser(null)
        return
      }
      void onOtherTabLogin()
    })
    channel.current = authChannel

    manager?.events.addUserSignedOut(onSignedOut)
    manager?.events.addAccessTokenExpiring(onTokenExpiring)
    manager?.events.addAccessTokenExpired(onTokenExpired)
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      cancelled = true
      authChannel.close()
      if (channel.current === authChannel) channel.current = null
      manager?.events.removeUserSignedOut(onSignedOut)
      manager?.events.removeAccessTokenExpiring(onTokenExpiring)
      manager?.events.removeAccessTokenExpired(onTokenExpired)
      document.removeEventListener('visibilitychange', onVisible)
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
        channel.current?.post('login')
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
    channel.current?.post('logout')
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

  return (
    <AuthContext.Provider value={value}>
      {children}
      <SessionExpiredDialog />
    </AuthContext.Provider>
  )
}
