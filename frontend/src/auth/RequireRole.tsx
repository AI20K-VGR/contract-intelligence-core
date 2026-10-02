import { Navigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { homePath, type AppRole } from './session'
import { useAuth } from './useAuth'

export function RequireRole({
  allow,
  children,
  fallback,
}: {
  allow: AppRole
  children: ReactNode
  /** Shown instead of redirecting home when the role does not match (e.g. a 403 page). */
  fallback?: ReactNode
}) {
  const { user } = useAuth()
  if (!user) {
    return <Navigate to="/" replace />
  }
  if (user.role !== allow) {
    return fallback ?? <Navigate to={homePath(user.role)} replace />
  }
  return children
}
