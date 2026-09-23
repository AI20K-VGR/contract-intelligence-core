import { Navigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { homePath, type AppRole } from './session'
import { useAuth } from './useAuth'

export function RequireRole({
  allow,
  children,
}: {
  allow: AppRole
  children: ReactNode
}) {
  const { user } = useAuth()
  if (!user) {
    return <Navigate to="/" replace />
  }
  if (user.role !== allow) {
    return <Navigate to={homePath(user.role)} replace />
  }
  return children
}
