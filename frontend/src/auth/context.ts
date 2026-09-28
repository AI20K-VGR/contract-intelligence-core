import { createContext } from 'react'
import type { SessionUser } from './session'

export type AuthContextValue = {
  user: SessionUser | null
  ready: boolean
  configured: boolean
  loginWithSso: (email: string) => Promise<void>
  completeSsoCallback: () => Promise<SessionUser>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
