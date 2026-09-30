import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { AppLayout } from './AppLayout'

/** Mọi vai trò dùng chung một vỏ; khác nhau chỉ ở mục điều hướng theo quyền. */
export function AppShell() {
  const { user } = useAuth()
  if (!user) {
    return <Navigate to="/" replace />
  }
  return <AppLayout role={user.role} />
}
