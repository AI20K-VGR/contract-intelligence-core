import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from './icons'

type SidebarLogoutProps = {
  className: string
}

export function SidebarLogout({ className }: SidebarLogoutProps) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <button
      className={className}
      type="button"
      onClick={() => {
        void handleLogout()
      }}
    >
      <MaterialIcon name="logout" className="text-[20px]" />
      <span>Đăng xuất</span>
    </button>
  )
}
