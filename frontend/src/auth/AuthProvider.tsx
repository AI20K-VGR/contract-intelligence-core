import { useMemo, useState, type ReactNode } from 'react'
import { AuthContext } from './context'
import {
  clearSession,
  delay,
  DEMO_USERS,
  loadSession,
  resolveEmailLogin,
  saveSession,
  type AppRole,
  type SessionUser,
} from './session'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState(() => loadSession())

  const value = useMemo(
    () => ({
      user,
      async loginAs(role: AppRole) {
        await delay(400)
        const next = DEMO_USERS[role]
        saveSession(next)
        setUser(next)
        return next
      },
      async loginWithEmail(email: string) {
        await delay(700)
        const result = resolveEmailLogin(email)
        if (result.ok === false) {
          throw new Error(result.message)
        }
        const next: SessionUser = result.user
        saveSession(next)
        setUser(next)
        return next
      },
      logout() {
        clearSession()
        setUser(null)
      },
    }),
    [user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
