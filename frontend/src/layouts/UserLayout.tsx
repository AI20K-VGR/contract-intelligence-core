import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AccountMenu } from '../components/AccountMenu'
import { MaterialIcon } from '../components/icons'
import { SidebarLogout } from '../components/SidebarLogout'

const navItems = [
  { to: '/ho-so-cua-toi', icon: 'folder', label: 'Hồ sơ của tôi' },
  {
    to: '/duoc-chia-se-voi-toi',
    icon: 'folder_shared',
    label: 'Được chia sẻ với tôi',
  },
  {
    to: '/tim-kiem-xuyen-ho-so',
    icon: 'saved_search',
    label: 'Tìm kiếm xuyên hồ sơ',
  },
  { to: '/cai-dat', icon: 'settings', label: 'Cài đặt' },
] as const

function navClassName(isActive: boolean) {
  return [
    'flex items-center gap-space-md px-space-md py-space-sm rounded-lg transition-colors',
    isActive
      ? 'bg-surface-container-high text-on-primary-fixed font-title-sm font-semibold'
      : 'text-on-primary-container hover:bg-surface-container-high hover:text-on-primary-fixed font-body-md text-body-md',
  ].join(' ')
}

export function UserLayout() {
  const location = useLocation()

  return (
    <div className="bg-surface font-body-md text-on-surface antialiased min-h-screen">
      <aside className="fixed left-0 top-0 h-full w-72 bg-primary-container z-50 flex flex-col justify-between select-none">
        <div className="flex flex-col">
          <div className="px-gutter pt-gutter pb-gutter-sm flex flex-col gap-space-xs">
            <div className="flex items-center gap-space-sm">
              <MaterialIcon
                name="gavel"
                className="text-primary-fixed text-[24px]"
              />
              <span className="font-title-sm text-title-sm text-primary-fixed tracking-wider uppercase font-semibold">
                Lexis Intelligence
              </span>
            </div>
            <span className="font-label-sm text-label-sm text-on-primary-container uppercase tracking-widest pl-7 font-medium">
              Legal Contract AI
            </span>
          </div>

          <nav className="flex flex-col gap-space-xs px-space-md mt-space-md">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  navClassName(
                    item.to === '/ho-so-cua-toi'
                      ? isActive ||
                          location.pathname === '/doi-soat-xung-dot' ||
                          location.pathname === '/tao-ho-so' ||
                          location.pathname.startsWith('/xac-nhan-manifest') ||
                          location.pathname === '/tien-trinh-phan-tich' ||
                          location.pathname.startsWith('/cau-truc/') ||
                          location.pathname.startsWith('/ocr/')
                      : isActive,
                  )
                }
              >
                <MaterialIcon name={item.icon} className="text-[20px]" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="flex flex-col">
          <div className="p-space-md m-space-md mb-0 bg-tertiary-container/50 rounded-lg flex items-center justify-between">
            <div className="flex flex-col gap-space-xs">
              <span className="font-label-sm text-label-sm text-primary-fixed uppercase tracking-wider font-semibold">
                Gói Doanh Nghiệp
              </span>
              <span className="font-code-sm text-code-sm text-on-primary-container">
                SLA 99.9% • SOC2 Type II
              </span>
            </div>
            <MaterialIcon
              name="verified_user"
              className="text-primary-fixed-dim text-[18px]"
            />
          </div>
          <div className="px-space-md pb-space-md pt-space-sm">
            <SidebarLogout className="w-full flex items-center gap-space-md px-space-md py-space-sm rounded-lg text-on-primary-container hover:bg-surface-container-high hover:text-on-primary-fixed transition-colors font-body-md text-body-md" />
          </div>
        </div>
      </aside>

      <div className="pl-72">
        <header className="fixed top-0 left-72 right-0 h-16 bg-surface/90 backdrop-blur-md z-40 flex items-center justify-end px-margin">
          <div className="flex items-center gap-space-lg">
            <button
              aria-label="Thông báo"
              className="relative flex items-center justify-center p-space-sm text-on-surface-variant hover:text-on-surface transition-colors"
              type="button"
            >
              <MaterialIcon name="notifications" className="text-[22px]" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-error" />
            </button>
            <AccountMenu
              gapClassName="gap-space-md"
              nameClassName="font-title-sm text-title-sm text-on-surface leading-none"
              emailClassName="font-code-sm text-code-sm text-on-surface-variant leading-none mt-1"
            />
          </div>
        </header>

        <main className="w-full pt-16 bg-surface px-margin min-h-screen">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
