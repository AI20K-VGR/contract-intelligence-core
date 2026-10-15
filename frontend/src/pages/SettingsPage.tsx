import { useSearchParams } from 'react-router-dom'
import { FontSizePicker } from '../components/FontSizePicker'
import { MaterialIcon } from '../components/icons'
import { PalettePicker } from '../components/PalettePicker'
import { ReadingSettings } from '../components/ReadingSettings'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

/* Mục con của Cài đặt; mục đang mở nằm trên đường dẫn (?muc=…) để tải lại vẫn giữ. */
const SECTIONS = [
  { id: 'giao-dien', label: 'Giao diện', icon: 'palette' },
  { id: 'doc-hop-dong', label: 'Đọc hợp đồng', icon: 'chrome_reader_mode' },
] as const

type SectionId = (typeof SECTIONS)[number]['id']

function parseSection(raw: string | null): SectionId {
  return SECTIONS.find((section) => section.id === raw)?.id ?? 'giao-dien'
}

export function SettingsPage() {
  usePageTitle('Cài đặt')
  const titleInHeader = useHeaderShowsPageTitle()
  const [params, setParams] = useSearchParams()
  const active = parseSection(params.get('muc'))

  return (
    <div className="flex flex-col gap-space-md max-w-5xl">
      {titleInHeader ? null : (
        <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
          Cài đặt
        </h1>
      )}

      {/* Thanh tab cùng kiểu với bộ lọc ở trang Quyền truy cập. */}
      <nav
        aria-label="Mục cài đặt"
        className="inline-flex flex-wrap items-center gap-1 self-start rounded-lg bg-surface-container-low p-1"
      >
        {SECTIONS.map((section) => {
          const selected = section.id === active
          return (
            <button
              key={section.id}
              aria-current={selected ? 'page' : undefined}
              className={`flex items-center gap-1.5 rounded px-3 py-1 font-label-sm text-label-sm uppercase tracking-wide transition-colors ${
                selected
                  ? 'bg-surface-container-lowest font-semibold text-on-surface shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
              type="button"
              onClick={() => setParams({ muc: section.id }, { replace: true })}
            >
              <MaterialIcon name={section.icon} className="text-[16px]" />
              {section.label}
            </button>
          )
        })}
      </nav>

      {active === 'giao-dien' ? (
        <>
          <PalettePicker />
          <FontSizePicker />
        </>
      ) : null}
      {active === 'doc-hop-dong' ? <ReadingSettings /> : null}
    </div>
  )
}
