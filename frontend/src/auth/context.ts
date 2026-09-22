import { createContext } from 'react'
import type { AppRole, SessionUser } from './session'

export type AuthContextValue = {
  user: SessionUser | null
  loginAs: (role: AppRole) => Promise<SessionUser>
  loginWithEmail: (email: string) => Promise<SessionUser>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
