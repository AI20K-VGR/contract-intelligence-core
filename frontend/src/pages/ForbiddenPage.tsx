import { MaterialIcon } from '../components/icons'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

/** 403 inside the app shell: the user is signed in but lacks the role. */
export function ForbiddenPage({
  title = 'Không có quyền truy cập',
  message = 'Trang này chỉ dành cho quản trị viên. Liên hệ quản trị viên nếu bạn cần quyền.',
}: {
  title?: string
  message?: string
}) {
  usePageTitle(title)
  const titleInHeader = useHeaderShowsPageTitle()

  return (
    <div className="flex flex-col gap-space-md max-w-3xl">
      {titleInHeader ? null : (
        <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
          {title}
        </h1>
      )}

      <section
        role="alert"
        className="bg-surface-container-lowest rounded-xl shadow-sm px-space-lg py-space-xl flex flex-col items-start gap-space-md"
      >
        <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-error-container text-on-error-container">
          <MaterialIcon name="block" className="text-[24px]" />
        </span>
        <div className="flex flex-col gap-space-xs">
          <p className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">
            403 Forbidden
          </p>
          <h2 className="font-title-sm text-title-sm text-on-surface">
            {title}
          </h2>
          <p className="max-w-xl font-body-sm text-body-sm text-on-surface-variant">
            {message}
          </p>
        </div>
      </section>
    </div>
  )
}
