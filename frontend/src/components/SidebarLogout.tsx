import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import type { UserRole } from '../auth/session'
import { MaterialIcon } from './icons'

const roleLabel: Record<UserRole, string> = {
  OPERATOR: 'Vận hành',
  REVIEWER: 'Thẩm định',
  ADMINISTRATOR: 'Quản trị',
}

const row =
  'flex w-full items-center gap-space-md rounded px-space-md py-space-sm font-body-md text-body-md'

const toneClass = {
  inverse: {
    role: 'bg-white/10 text-surface-container-highest',
    button:
      'text-surface-container-highest transition-colors hover:bg-tertiary-container hover:text-surface',
  },
  surface: {
    role: 'bg-surface-container-high text-on-surface',
    button:
      'text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface',
  },
} as const

type SidebarLogoutProps = {
  tone: keyof typeof toneClass
}

export function SidebarLogout({ tone }: SidebarLogoutProps) {
  const { logout, user } = useAuth()
  const navigate = useNavigate()
  const role = user ? roleLabel[user.backendRole] : ''
  const colors = toneClass[tone]

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <div className="flex w-full flex-col gap-1">
      {role ? (
        <div className={`${row} ${colors.role}`}>
          <MaterialIcon name="badge" className="text-[20px]" />
          <span>{role}</span>
        </div>
      ) : null}
      <button
        className={`${row} ${colors.button}`}
        type="button"
        onClick={() => {
          void handleLogout()
        }}
      >
        <MaterialIcon name="logout" className="text-[20px]" />
        <span>Đăng xuất</span>
      </button>
    </div>
  )
}
