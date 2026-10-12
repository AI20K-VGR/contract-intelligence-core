import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'
import { PalettePicker } from '../components/PalettePicker'

export function SettingsPage() {
  usePageTitle('Cài đặt')
  const titleInHeader = useHeaderShowsPageTitle()

  return (
    <div className="flex flex-col gap-space-md max-w-4xl">
      {titleInHeader ? null : (
        <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
          Cài đặt
        </h1>
      )}

      <PalettePicker />
    </div>
  )
}
