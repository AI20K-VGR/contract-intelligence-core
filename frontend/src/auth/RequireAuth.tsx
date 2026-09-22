import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'

export function RequireAuth() {
  const { user, ready } = useAuth()
  if (!ready) {
    return null
  }
  if (!user) {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}
