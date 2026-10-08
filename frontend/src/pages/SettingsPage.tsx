import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'
import { useAuth } from '../auth/useAuth'
import { PalettePicker } from '../components/PalettePicker'
import { TenantLexiconPanel } from '../components/TenantLexiconPanel'

export function SettingsPage() {
  usePageTitle('Cài đặt')
  const titleInHeader = useHeaderShowsPageTitle()
  const { user } = useAuth()

  return (
    <div className="flex flex-col gap-space-md max-w-3xl">
      {titleInHeader ? null : (
        <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
          Cài đặt
        </h1>
      )}

      <PalettePicker />

      {user?.tenantId ? (
        <TenantLexiconPanel tenantId={user.tenantId} actorId={user.id} />
      ) : null}
    </div>
  )
}
