import { MaterialIcon } from '../components/icons'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

export function SettingsPage() {
  usePageTitle('Cài đặt')
  const titleInHeader = useHeaderShowsPageTitle()

  return (
    <div className="flex flex-col gap-space-md max-w-3xl">
      {titleInHeader ? null : (
        <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
          Cài đặt
        </h1>
      )}

      <section className="bg-surface-container-lowest rounded-xl shadow-sm px-space-lg py-space-xl flex flex-col items-start gap-space-md">
        <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-surface-container-low text-secondary">
          <MaterialIcon name="settings" className="text-[24px]" />
        </span>
        <div className="flex flex-col gap-space-xs">
          <p className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">
            Sắp ra mắt
          </p>
          <h2 className="font-title-sm text-title-sm text-on-surface">
            Trang cài đặt chưa mở
          </h2>
          <p className="max-w-xl font-body-sm text-body-sm text-on-surface-variant">
            Các tùy chọn hệ thống sẽ có ở đây khi phần này được đưa vào sử dụng.
          </p>
        </div>
      </section>
    </div>
  )
}
