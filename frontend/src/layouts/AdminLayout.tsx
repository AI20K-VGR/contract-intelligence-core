import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AccountMenu } from '../components/AccountMenu'
import { MaterialIcon } from '../components/icons'
import { SidebarLogout } from '../components/SidebarLogout'
import {
  PageTitleProvider,
  useCurrentPageTitle,
} from '../hooks/usePageTitle'

const navItems = [
  { to: '/tong-quan', icon: 'dashboard', label: 'Tổng quan' },
  { to: '/ho-so', icon: 'folder_shared', label: 'Hồ sơ', locked: true },
  { to: '/quyen-truy-cap', icon: 'lock', label: 'Quyền truy cập' },
  { to: '/nhat-ky-hoat-dong', icon: 'history_edu', label: 'Nhật ký hoạt động' },
  {
    to: '/nguoi-dung-phan-quyen',
    icon: 'manage_accounts',
    label: 'Người dùng & Phân quyền',
  },
  { to: '/cai-dat', icon: 'settings', label: 'Cài đặt' },
] as const

function HeaderPageTitle() {
  const title = useCurrentPageTitle()
  if (!title) return null
  return (
    <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
      {title}
    </h1>
  )
}

function navClassName(isActive: boolean) {
  return [
    'flex items-center gap-space-md px-space-md py-space-sm rounded transition-colors whitespace-nowrap',
    isActive
      ? 'bg-inverse-surface text-surface font-title-sm text-body-md'
      : 'text-surface-container-highest hover:bg-tertiary-container hover:text-surface font-body-md text-body-md',
  ].join(' ')
}

export function AdminLayout() {
  const location = useLocation()
  const dossierSection =
    ['/ho-so', '/tao-ho-so', '/doi-soat-xung-dot'].includes(
      location.pathname,
    ) ||
    location.pathname.startsWith('/tien-trinh-phan-tich') ||
    location.pathname.startsWith('/cau-truc/') ||
    location.pathname.startsWith('/ocr/') ||
    location.pathname.startsWith('/xac-nhan-manifest')

  return (
    <PageTitleProvider>
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
          <HeaderPageTitle />

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
    </PageTitleProvider>
  )
}
