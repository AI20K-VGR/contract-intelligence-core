import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { AdminLayout } from './AdminLayout'
import { UserLayout } from './UserLayout'

export function AppShell() {
  const { user } = useAuth()
  if (!user) {
    return <Navigate to="/" replace />
  }
  return user.role === 'admin' ? <AdminLayout /> : <UserLayout />
}
