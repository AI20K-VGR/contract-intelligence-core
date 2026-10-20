import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from './icons'

type AccountMenuProps = {
  nameClassName: string
  emailClassName: string
  gapClassName: string
}

export function AccountMenu({
  nameClassName,
  emailClassName,
  gapClassName,
}: AccountMenuProps) {
  const { user } = useAuth()

  if (!user) return null

  return (
    <div className={`flex items-center ${gapClassName}`}>
      {/* Laptop nhỏ: chỉ còn avatar, nhường chỗ cho tiêu đề và đường dẫn. */}
      <div className="hidden flex-col items-end whitespace-nowrap text-right xl:flex">
        <span className={nameClassName}>{user.name}</span>
        <span className={emailClassName}>{user.email}</span>
      </div>
      <div
        className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center shrink-0"
        title={`${user.name} · ${user.email}`}
      >
        <MaterialIcon name="person" className="text-brand-700 text-[18px]" />
      </div>
    </div>
  )
}
