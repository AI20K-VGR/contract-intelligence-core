import { Link } from 'react-router-dom'
import { MaterialIcon } from '../components/icons'
import { usePageTitle } from '../hooks/usePageTitle'

export function PlaceholderPage({
  title,
  actionTo,
  actionLabel,
}: {
  title: string
  actionTo?: string
  actionLabel?: string
}) {
  usePageTitle(title)

  return (
    <div className="flex flex-col gap-space-sm">
      <div className="flex items-center justify-between gap-space-md">
        <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
          {title}
        </h1>
        {actionTo && actionLabel ? (
          <Link
            className="flex items-center gap-space-xs px-space-md py-2 bg-primary-container text-on-primary font-title-sm text-body-sm rounded shadow-sm hover:bg-tertiary-container transition-colors"
            to={actionTo}
          >
            <MaterialIcon name="add" className="text-[18px]" />
            <span>{actionLabel}</span>
          </Link>
        ) : null}
      </div>
      <p className="font-body-sm text-body-sm text-secondary">
        Giao diện Stitch cho mục này sẽ được ghép khi bạn gửi code.
      </p>
    </div>
  )
}
