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
      <div className="flex flex-col items-end text-right">
        <span className={nameClassName}>{user.name}</span>
        <span className={emailClassName}>{user.email}</span>
      </div>
      <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0">
        <MaterialIcon name="person" className="text-on-primary text-[18px]" />
      </div>
    </div>
  )
}
