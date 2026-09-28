import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { dossiersLabel, dossiersPath, type AppRole, type UserRole } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { AccountMenu } from '../components/AccountMenu'
import { MaterialIcon } from '../components/icons'
import { SidebarLogout } from '../components/SidebarLogout'
import { PageTitleProvider, useCurrentPageTitle } from '../hooks/usePageTitle'

/*
 * Vỏ ứng dụng dùng chung cho mọi vai trò: cùng sidebar, header, khoảng cách.
 * Chỉ danh sách mục điều hướng khác nhau theo quyền — admin có thêm Tổng quan,
 * Quyền truy cập, Nhật ký hoạt động, Người dùng & Phân quyền.
 */

type NavItem = { to: string; icon: string; label: string }

function navItemsFor(role: UserRole): NavItem[] {
  const dossiers =
    role === 'ADMINISTRATOR'
      ? { to: '/ho-so', icon: 'folder_shared', label: 'Hồ sơ' }
      : { to: '/ho-so-cua-toi', icon: 'folder_shared', label: 'Hồ sơ của tôi' }
  const shared: NavItem[] = [
    dossiers,
    {
      to: '/nhat-ky-hoat-dong',
      icon: 'history_edu',
      label: 'Nhật ký hoạt động',
    },
  ]
  if (role === 'OPERATOR') {
    shared.splice(1, 0, {
      to: '/quyen-truy-cap',
      icon: 'lock',
      label: 'Quyền truy cập',
    })
  }
  if (role === 'ADMINISTRATOR') {
    shared.unshift({ to: '/tong-quan', icon: 'dashboard', label: 'Tổng quan' })
    shared.splice(2, 0, {
      to: '/quyen-truy-cap',
      icon: 'lock',
      label: 'Quyền truy cập',
    })
    shared.push({
      to: '/nguoi-dung-phan-quyen',
      icon: 'manage_accounts',
      label: 'Người dùng & Phân quyền',
    })
  }
  shared.push({ to: '/cai-dat', icon: 'settings', label: 'Cài đặt' })
  return shared
}

/** Các trang con của luồng hồ sơ: vẫn sáng mục "Hồ sơ" trên sidebar. */
function inDossierSection(pathname: string, role: AppRole) {
  return (
    [dossiersPath(role), '/tao-ho-so', '/doi-soat-xung-dot'].includes(
      pathname,
    ) ||
    pathname.startsWith('/tien-trinh-phan-tich') ||
    pathname.startsWith('/cau-truc/') ||
    pathname.startsWith('/ocr/') ||
    pathname.startsWith('/xac-nhan-manifest')
  )
}

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

export function AppLayout({ role }: { role: AppRole }) {
  const { user } = useAuth()
  const location = useLocation()
  const navItems = navItemsFor(
    user?.backendRole ?? (role === 'admin' ? 'ADMINISTRATOR' : 'OPERATOR'),
  )
  const dossiersTo = dossiersPath(role)
  const dossierSection = inDossierSection(location.pathname, role)
  const structurePage = location.pathname.startsWith('/cau-truc/')
  const fillViewport =
    structurePage || location.pathname === '/doi-soat-xung-dot'

  return (
    <PageTitleProvider>
      <div
        className={`bg-background font-body-md text-on-surface antialiased ${
          fillViewport ? 'h-screen overflow-hidden' : 'min-h-screen'
        }`}
      >
        <aside
          aria-label="Điều hướng chính"
          className="fixed left-0 top-0 h-full w-64 bg-primary-container text-surface flex flex-col z-50 shadow-[0_1px_8px_rgba(0,0,0,0.08)]"
        >
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
                title={item.to === dossiersTo ? dossiersLabel(role) : undefined}
                className={() => {
                  const active =
                    item.to === dossiersTo
                      ? location.pathname === dossiersTo || dossierSection
                      : location.pathname === item.to
                  return navClassName(active)
                }}
              >
                <span className="flex items-center gap-space-md">
                  <MaterialIcon name={item.icon} className="text-[20px]" />
                  <span>{item.label}</span>
                </span>
              </NavLink>
            ))}
          </nav>

          <div className="px-space-sm pb-space-md">
            <SidebarLogout tone="inverse" />
          </div>
        </aside>

        <div className={fillViewport ? 'h-full pl-64' : 'pl-64'}>
          <header className="fixed top-0 left-64 right-0 h-16 bg-surface/90 backdrop-blur-md z-40 flex items-center justify-between px-gutter shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
            <HeaderPageTitle />

            <div className="flex items-center gap-space-md">
              <button
                aria-label="Thông báo"
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

          <main
            className={
              fillViewport
                ? 'flex h-screen flex-col overflow-hidden bg-background px-gutter pb-space-md pt-16'
                : 'w-full min-h-screen bg-background px-gutter py-space-lg pt-16'
            }
          >
            <Outlet />
          </main>
        </div>
      </div>
    </PageTitleProvider>
  )
}
