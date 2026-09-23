import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { SidebarLogout } from '../components/SidebarLogout'

const navItems = [
  { to: '/ho-so-hop-dong', icon: 'folder_open', label: 'Hồ sơ Hợp đồng' },
  {
    to: '/trung-tam-phan-tich',
    icon: 'analytics',
    label: 'Trung tâm Phân tích',
  },
  {
    to: '/kho-dieu-khoan-mau',
    icon: 'library_books',
    label: 'Kho Điều khoản Mẫu',
  },
  {
    to: '/tuan-thu-rui-ro',
    icon: 'verified_user',
    label: 'Tuân thủ & Rủi ro',
  },
  {
    to: '/nhat-ky-phap-ly',
    icon: 'history_edu',
    label: 'Nhật ký Pháp lý',
  },
] as const

function navClassName(isActive: boolean) {
  return [
    'flex items-center gap-space-md px-space-md py-space-sm rounded transition-colors',
    isActive
      ? 'bg-primary-container text-on-primary font-semibold'
      : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface',
  ].join(' ')
}

export function ReviewLayout() {
  const { user } = useAuth()
  const home = user ? dossiersPath(user.role) : '/'
  const location = useLocation()

  return (
    <div className="bg-surface font-body-md text-on-surface antialiased min-h-screen">
      <aside className="fixed left-0 top-0 h-full w-64 bg-surface-container-lowest z-50 flex flex-col shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
        <div className="h-14 px-gutter flex items-center gap-space-sm bg-primary-container text-on-primary">
          <MaterialIcon
            name="gavel"
            className="text-[20px] text-on-tertiary-container"
          />
          <div className="flex flex-col">
            <span className="font-title-sm text-title-sm uppercase tracking-wider text-on-primary font-bold">
              Lexis Sovereign
            </span>
            <span className="font-label-sm text-label-sm text-on-primary-container uppercase">
              Trí tuệ Pháp chế
            </span>
          </div>
        </div>

        <div className="px-space-md py-space-sm">
          <div className="px-space-sm py-space-xs font-label-sm text-label-sm uppercase text-secondary font-semibold">
            Phân hệ Nghiệp vụ
          </div>
        </div>

        <nav className="flex-1 px-space-sm space-y-space-xs">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                navClassName(
                  item.to === '/ho-so-hop-dong'
                    ? isActive ||
                        location.pathname === '/doi-soat-trich-dan' ||
                        location.pathname === '/nhan-xet-chinh-sua' ||
                        location.pathname === '/chinh-sua-trich-dan'
                    : isActive,
                )
              }
            >
              <MaterialIcon name={item.icon} className="text-[18px]" />
              <span className="font-body-md text-body-md">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-space-md m-space-sm bg-surface-container-low rounded flex flex-col gap-space-xs">
          <div className="flex items-center justify-between font-label-sm text-label-sm">
            <span className="text-secondary">Chứng thực SOC2</span>
            <span className="font-code-sm text-code-sm text-on-tertiary-fixed-variant">
              SVR-2024-VN
            </span>
          </div>
          <div className="font-label-sm text-label-sm text-on-surface-variant">
            Mã hóa đầu cuối 256-bit AES
          </div>
        </div>

        <div className="px-space-sm pb-space-md">
          <SidebarLogout className="w-full flex items-center gap-space-md px-space-md py-space-sm rounded text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors font-body-md text-body-md" />
        </div>
      </aside>

      <div className="pl-64">
        <header className="fixed top-0 left-64 right-0 h-14 bg-surface-container-lowest z-40 shadow-[0_1px_8px_rgba(0,0,0,0.04)] flex items-center justify-between px-gutter">
          <div className="flex items-center gap-2 text-secondary font-label-sm text-label-sm">
            <Link
              className="flex items-center hover:text-on-surface transition-colors"
              to={home}
            >
              <MaterialIcon name="home" className="text-[18px]" />
            </Link>
            <span>/</span>
            <span className="text-on-surface font-medium">Hồ sơ Hợp đồng</span>
          </div>

          <div className="flex items-center gap-space-lg ml-auto">
            <div className="flex items-center gap-space-sm px-space-md py-1 rounded bg-surface-container-low">
              <div className="flex -space-x-2">
                <div className="w-6 h-6 rounded-[9999px] bg-primary-container text-on-primary flex items-center justify-center font-label-sm text-label-sm font-semibold ring-1 ring-surface-container-lowest">
                  HN
                </div>
                <div className="w-6 h-6 rounded-[9999px] bg-tertiary-container text-on-tertiary flex items-center justify-center font-label-sm text-label-sm font-semibold ring-1 ring-surface-container-lowest">
                  TL
                </div>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-[9999px] bg-[#059669]" />
                <span className="font-label-sm text-label-sm text-on-surface-variant">
                  2 người đang xem
                </span>
              </div>
            </div>

            <div className="flex items-center gap-space-sm">
              <button
                className="w-8 h-8 rounded flex items-center justify-center text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors relative"
                type="button"
              >
                <MaterialIcon name="notifications" className="text-[20px]" />
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-[9999px]" />
              </button>
              <button
                className="w-8 h-8 rounded flex items-center justify-center text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors"
                type="button"
              >
                <MaterialIcon name="help_outline" className="text-[20px]" />
              </button>
            </div>

            {user ? (
              <div className="flex items-center gap-space-md pl-space-sm">
                <div className="flex flex-col text-right">
                  <span className="font-title-sm text-title-sm text-on-surface leading-tight">
                    {user.name}
                  </span>
                  <span className="font-label-sm text-label-sm text-secondary leading-tight">
                    {user.role === 'admin'
                      ? 'Quản trị viên'
                      : 'Chuyên viên Pháp chế Cấp cao'}
                  </span>
                </div>
                <div className="w-8 h-8 rounded-[9999px] bg-primary flex items-center justify-center">
                  <MaterialIcon
                    name="person"
                    className="text-on-primary text-[18px]"
                  />
                </div>
              </div>
            ) : null}
          </div>
        </header>

        <main className="w-full pt-14 bg-surface min-h-screen px-gutter py-space-lg">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
