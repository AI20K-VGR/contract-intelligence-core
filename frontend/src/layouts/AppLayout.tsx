import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  dossiersLabel,
  dossiersPath,
  type AppRole,
  type UserRole,
} from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { AccountMenu } from '../components/AccountMenu'
import { MaterialIcon } from '../components/icons'
import { NotificationBell } from '../components/NotificationBell'
import { SidebarLogout } from '../components/SidebarLogout'
import {
  PageTitleProvider,
  useCurrentBreadcrumb,
  useCurrentPageTitle,
  type Crumb,
} from '../hooks/usePageTitle'

/*
 * Vỏ ứng dụng dùng chung cho mọi vai trò: cùng sidebar, header, khoảng cách.
 * Chỉ danh sách mục điều hướng khác nhau theo quyền — admin có thêm Tổng quan,
 * Quyền truy cập, Nhật ký hoạt động, Người dùng & Phân quyền và mục Quản trị
 * → Giám sát hệ thống (/admin/monitoring).
 */

/** `section`: items sharing one are grouped under that heading. */
type NavItem = { to: string; icon: string; label: string; section?: string }

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
  if (role === 'ADMINISTRATOR') {
    shared.push({
      to: '/admin/monitoring',
      icon: 'monitoring',
      label: 'Giám sát hệ thống',
      section: 'Quản trị',
    })
  }
  return shared
}

/** Trang dùng giao diện mới theo màu chủ đạo ở Cài đặt (lớp theme-soft trong index.css). */
const MONO_PAGES = [
  '/tong-quan',
  '/ho-so',
  '/ho-so-cua-toi',
  '/quyen-truy-cap',
  '/nhat-ky-hoat-dong',
  '/nguoi-dung-phan-quyen',
  '/cai-dat',
  '/admin/monitoring',
]

/** Trang có mã hồ sơ trong đường dẫn: so theo phần đầu. */
const MONO_PAGE_PREFIXES = ['/cau-truc/']

/** Các trang con của luồng hồ sơ: vẫn sáng mục "Hồ sơ" trên sidebar. */
function inDossierSection(pathname: string, role: AppRole) {
  return (
    [dossiersPath(role), '/tao-ho-so', '/doi-soat-xung-dot'].includes(
      pathname,
    ) ||
    pathname.startsWith('/tien-trinh-phan-tich') ||
    pathname.startsWith('/cau-truc/') ||
    pathname.startsWith('/lich-su-hoi-dap/') ||
    pathname.startsWith('/ocr/') ||
    pathname.startsWith('/xac-nhan-manifest')
  )
}

function HeaderPageTitle() {
  const title = useCurrentPageTitle()
  const crumbs = useCurrentBreadcrumb()
  if (crumbs?.length) return <HeaderBreadcrumb crumbs={crumbs} />
  if (!title) return null
  return (
    <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
      {title}
    </h1>
  )
}

/** Đường dẫn một dòng thay cho tiêu đề, vd. Hồ sơ › abc › Cấu trúc cây. */
function HeaderBreadcrumb({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="Đường dẫn" className="mr-space-md min-w-0">
      <ol className="flex min-w-0 items-center gap-1.5 font-headline-lg text-headline-lg tracking-tight">
        {crumbs.map((crumb, index) => {
          const first = index === 0
          const last = index === crumbs.length - 1
          return (
            <li
              key={`${index}-${crumb.label}`}
              // Tên hồ sơ dài thì cắt tên, giữ nguyên mục đầu và mục cuối.
              className={`flex items-center gap-1.5 ${first || last ? 'shrink-0' : 'min-w-0'}`}
            >
              {first ? null : (
                <MaterialIcon
                  name="chevron_right"
                  className="shrink-0 text-[22px] text-outline"
                />
              )}
              {last ? (
                <h1 aria-current="page" className="truncate text-on-surface">
                  {crumb.label}
                </h1>
              ) : crumb.to ? (
                <Link
                  className="truncate font-normal text-on-surface-variant transition-colors hover:text-primary"
                  to={crumb.to}
                >
                  {crumb.label}
                </Link>
              ) : (
                <span className="truncate font-normal text-on-surface-variant">
                  {crumb.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

function navClassName(isActive: boolean) {
  return [
    'flex items-center gap-space-md px-space-md py-2 rounded-[8px] text-[14px] transition-colors whitespace-nowrap',
    isActive
      ? 'bg-white text-brand-700 font-medium shadow-[0_1px_3px_rgba(0,0,0,0.06)]'
      : 'text-tone-600 hover:bg-brand-100 hover:text-tone-900',
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
  const mono =
    MONO_PAGES.includes(location.pathname) ||
    MONO_PAGE_PREFIXES.some((prefix) => location.pathname.startsWith(prefix))
  const fillViewport =
    structurePage ||
    location.pathname === '/doi-soat-xung-dot' ||
    location.pathname === '/admin/monitoring'

  return (
    <PageTitleProvider>
      <div
        className={`bg-background font-body-md text-on-surface antialiased ${mono ? 'theme-soft' : ''} ${
          fillViewport ? 'h-screen overflow-hidden' : 'min-h-screen'
        }`}
      >
        <aside
          aria-label="Điều hướng chính"
          className="fixed left-0 top-0 h-full w-64 bg-brand-50 text-tone-900 border-r border-brand-100 flex flex-col z-50"
        >
          <div className="h-16 flex items-center px-space-lg gap-space-sm">
            <span className="w-8 h-8 rounded-[8px] bg-brand-100 flex items-center justify-center shrink-0">
              <MaterialIcon
                name="shield"
                className="text-brand-700 text-[18px]"
              />
            </span>
            <div className="flex flex-col">
              <span className="text-[13px] font-semibold tracking-wide text-tone-900 uppercase">
                LEXIS INTELLIGENCE
              </span>
              <span className="text-[11px] text-tone-500 uppercase tracking-wide">
                Enterprise Legal AI
              </span>
            </div>
          </div>

          <div className="px-space-md py-space-xs">
            <div className="bg-brand-100 rounded-[8px] px-space-md py-1.5 flex items-center justify-between">
              <span className="text-[12px] text-tone-600 flex items-center gap-1">
                <MaterialIcon
                  name="verified_user"
                  className="text-[14px] text-[#1f9d6b]"
                />
                SOC2 Type II Active
              </span>
            </div>
          </div>

          <nav className="flex-1 px-space-sm py-space-md flex flex-col gap-1">
            {navItems.map((item, index) => [
              item.section && item.section !== navItems[index - 1]?.section ? (
                <p
                  key={`section-${item.section}`}
                  className="mt-space-md px-space-md pb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-tone-400"
                >
                  {item.section}
                </p>
              ) : null,
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
                  <MaterialIcon name={item.icon} className="text-[18px]" />
                  <span>{item.label}</span>
                </span>
              </NavLink>,
            ])}
          </nav>

          <div className="px-space-sm pb-space-md">
            <SidebarLogout tone="light" />
          </div>
        </aside>

        <div className={fillViewport ? 'h-full pl-64' : 'pl-64'}>
          <header className="fixed top-0 left-64 right-0 h-16 bg-white/90 backdrop-blur-md z-40 flex items-center justify-between px-gutter border-b border-tone-200">
            <HeaderPageTitle />

            <div className="flex items-center gap-space-md">
              <NotificationBell
                buttonClassName="w-9 h-9 rounded flex items-center justify-center text-secondary hover:bg-surface-container hover:text-on-surface relative transition-colors"
                dotClassName="absolute top-2 right-2 w-2 h-2 rounded-full bg-error"
              />
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
