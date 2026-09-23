import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AccountMenu } from '../components/AccountMenu'
import { MaterialIcon } from '../components/icons'
import { SidebarLogout } from '../components/SidebarLogout'

const navItems = [
  { to: '/tong-quan', icon: 'dashboard', label: 'Tổng quan' },
  {
    to: '/nguoi-dung-phan-quyen',
    icon: 'manage_accounts',
    label: 'Người dùng & Phân quyền',
  },
  { to: '/ho-so', icon: 'folder_shared', label: 'Hồ sơ', locked: true },
  { to: '/tao-ho-so', icon: 'cloud_upload', label: 'Tải lên' },
  { to: '/nhat-ky-hoat-dong', icon: 'history_edu', label: 'Nhật ký hoạt động' },
  { to: '/cai-dat', icon: 'settings', label: 'Cài đặt' },
] as const

function navClassName(isActive: boolean) {
  return [
    'flex items-center gap-space-md px-space-md py-space-sm rounded transition-colors',
    isActive
      ? 'bg-inverse-surface text-surface font-title-sm'
      : 'text-surface-container-highest hover:bg-tertiary-container hover:text-surface font-body-md text-body-md',
  ].join(' ')
}

export function AdminLayout() {
  const location = useLocation()
  const dossierSection = [
    '/ho-so',
    '/tien-trinh-phan-tich',
    '/doi-soat-xung-dot',
  ].includes(location.pathname)

  return (
    <div className="bg-background font-body-md text-on-surface antialiased min-h-screen">
      <aside className="fixed left-0 top-0 h-full w-64 bg-primary-container text-surface flex flex-col z-50 shadow-[0_1px_8px_rgba(0,0,0,0.08)]">
        <div className="h-16 flex items-center px-space-lg gap-space-sm">
          <MaterialIcon
            name="shield"
            className="text-primary-fixed text-[22px]"
          />
          <div className="flex flex-col">
            <span className="font-label-md text-label-md tracking-wider text-surface uppercase">
              LEXIS INTELLIGENCE
            </span>
            <span className="font-label-sm text-label-sm text-on-primary-container uppercase">
              Enterprise Legal AI
            </span>
          </div>
        </div>

        <div className="px-space-md py-space-xs">
          <div className="bg-tertiary-container/60 rounded px-space-md py-space-xs flex items-center justify-between">
            <span className="font-label-sm text-label-sm text-surface-variant flex items-center gap-1">
              <MaterialIcon
                name="verified_user"
                className="text-[14px] text-emerald-400"
              />
              SOC2 Type II Active
            </span>
          </div>
        </div>

        <nav className="flex-1 px-space-sm py-space-md flex flex-col gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={() => {
                const active =
                  item.to === '/ho-so'
                    ? location.pathname === '/ho-so' || dossierSection
                    : item.to === '/tao-ho-so'
                      ? location.pathname === '/tao-ho-so' ||
                        location.pathname.startsWith('/xac-nhan-manifest')
                      : location.pathname === item.to
                return 'locked' in item && item.locked
                  ? `${navClassName(active)} justify-between`
                  : navClassName(active)
              }}
            >
              <span className="flex items-center gap-space-md">
                <MaterialIcon name={item.icon} className="text-[20px]" />
                <span>{item.label}</span>
              </span>
              {'locked' in item && item.locked ? (
                <MaterialIcon
                  name="lock"
                  className="text-[16px] text-primary-fixed-dim"
                  title="Privacy-First Encrypted Storage"
                />
              ) : null}
            </NavLink>
          ))}
        </nav>

        <div className="px-space-sm pb-space-md">
          <SidebarLogout className="w-full flex items-center gap-space-md px-space-md py-space-sm rounded text-surface-container-highest hover:bg-tertiary-container hover:text-surface transition-colors font-body-md text-body-md" />
        </div>
      </aside>

      <div className="pl-64">
        <header className="fixed top-0 left-64 right-0 h-16 bg-surface/90 backdrop-blur-md z-40 flex items-center justify-between px-gutter shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
          <div className="flex items-center gap-space-lg">
            <div className="flex items-center gap-space-xs cursor-pointer py-space-xs px-space-sm rounded hover:bg-surface-container">
              <MaterialIcon
                name="corporate_fare"
                className="text-secondary text-[20px]"
              />
              <span className="font-title-sm text-title-sm text-on-surface">
                Tập đoàn Luật Apex & Đối tác
              </span>
              <MaterialIcon
                name="expand_more"
                className="text-outline text-[18px]"
              />
            </div>
            <div className="h-5 w-[1px] bg-outline-variant" />
            <div className="relative flex items-center">
              <MaterialIcon
                name="search"
                className="absolute left-3 text-outline text-[18px]"
              />
              <input
                className="w-96 pl-9 pr-space-md py-1.5 bg-surface-container-lowest text-on-surface rounded placeholder:text-outline font-body-sm text-body-sm focus:outline-none focus:ring-1 focus:ring-secondary"
                placeholder="Tra cứu hợp đồng, điều khoản, vụ việc..."
                type="search"
              />
            </div>
          </div>

          <div className="flex items-center gap-space-md">
            <button
              className="w-9 h-9 rounded flex items-center justify-center text-secondary hover:bg-surface-container hover:text-on-surface relative transition-colors"
              type="button"
            >
              <MaterialIcon name="notifications" className="text-[20px]" />
              <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-error" />
            </button>
            <div className="h-5 w-[1px] bg-outline-variant" />
            <AccountMenu
              gapClassName="gap-space-sm"
              nameClassName="font-label-md text-label-md text-on-surface leading-none"
              emailClassName="font-label-sm text-label-sm text-secondary leading-none mt-1"
            />
          </div>
        </header>

        <main className="w-full pt-16 bg-background min-h-screen px-gutter py-space-lg">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
