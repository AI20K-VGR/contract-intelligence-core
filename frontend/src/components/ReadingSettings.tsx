import { structureViews } from '../structure'
import {
  setReadingPrefs,
  useReadingPrefs,
  type ReadingPrefs,
} from '../structure/readingPrefs'
import { MaterialIcon } from './icons'

const card =
  'bg-surface-container-lowest rounded-xl shadow-sm px-space-lg py-space-lg flex flex-col gap-space-md'

function OptionCard({
  active,
  icon,
  label,
  hint,
  onClick,
}: {
  active: boolean
  icon: string
  label: string
  hint: string
  onClick: () => void
}) {
  return (
    <button
      aria-checked={active}
      className={`group flex items-start gap-space-sm rounded-lg border bg-surface-container-lowest p-space-md text-left transition-all ${
        active
          ? 'border-brand-600 ring-2 ring-brand-600/30'
          : 'border-outline-variant/60 hover:border-outline hover:shadow-sm'
      }`}
      role="radio"
      type="button"
      onClick={onClick}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-700">
        <MaterialIcon name={icon} className="text-[20px]" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="font-body-md text-body-md font-semibold text-on-surface">
          {label}
        </span>
        <span className="font-body-sm text-body-sm text-on-surface-variant">
          {hint}
        </span>
      </span>
      <MaterialIcon
        name={active ? 'check_circle' : 'radio_button_unchecked'}
        className={`text-[18px] ${
          active
            ? 'text-brand-600'
            : 'text-outline-variant group-hover:text-outline'
        }`}
      />
    </button>
  )
}

function ToggleRow({
  checked,
  label,
  hint,
  onChange,
}: {
  checked: boolean
  label: string
  hint: string
  onChange: (next: boolean) => void
}) {
  return (
    <button
      aria-checked={checked}
      className="flex w-full items-center gap-space-md px-space-md py-space-md text-left transition-colors hover:bg-tone-50"
      role="switch"
      type="button"
      onClick={() => onChange(!checked)}
    >
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="font-body-md text-body-md font-semibold text-on-surface">
          {label}
        </span>
        <span className="font-body-sm text-body-sm text-on-surface-variant">
          {hint}
        </span>
      </span>
      <span
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${checked ? 'bg-brand-600' : 'bg-tone-300'}`}
      >
        <span
          className={`absolute top-1 h-4 w-4 rounded-full bg-white shadow transition-all ${checked ? 'left-6' : 'left-1'}`}
        />
      </span>
    </button>
  )
}

export function ReadingSettings() {
  const prefs = useReadingPrefs()
  const views: {
    value: ReadingPrefs['openView']
    label: string
    icon: string
    hint: string
  }[] = [
    {
      value: 'last',
      label: 'Như lần trước',
      icon: 'history',
      hint: 'Mở đúng kiểu xem bạn dùng gần nhất.',
    },
    ...structureViews,
  ]

  return (
    <>
      <section className={card}>
        <div className="flex flex-col gap-space-xs">
          <h2 className="font-title-sm text-title-sm text-on-surface">
            Kiểu xem khi mở hợp đồng
          </h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Trong trang hợp đồng vẫn đổi kiểu xem được bất cứ lúc nào.
          </p>
        </div>
        <div
          aria-label="Kiểu xem khi mở hợp đồng"
          className="grid grid-cols-1 gap-space-md sm:grid-cols-2"
          role="radiogroup"
        >
          {views.map((view) => (
            <OptionCard
              key={view.value}
              active={prefs.openView === view.value}
              hint={view.hint}
              icon={view.icon}
              label={view.label}
              onClick={() => setReadingPrefs({ openView: view.value })}
            />
          ))}
        </div>
      </section>

      <section className={card}>
        <div className="flex flex-col gap-space-xs">
          <h2 className="font-title-sm text-title-sm text-on-surface">
            Khi đọc
          </h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Được nhớ trên trình duyệt này.
          </p>
        </div>
        <div className="flex flex-col divide-y divide-outline-variant/60 overflow-hidden rounded-lg border border-outline-variant/60">
          <ToggleRow
            checked={prefs.autoScroll}
            hint="Bấm vào trích dẫn trong câu trả lời thì mở nhánh và cuộn tới đúng điều khoản."
            label="Tự cuộn tới trích dẫn"
            onChange={(next) => setReadingPrefs({ autoScroll: next })}
          />
          <ToggleRow
            checked={prefs.highlightConflicts}
            hint="Đánh dấu điều khoản có xung đột và số xung đột trong từng nhánh."
            label="Tô sáng xung đột"
            onChange={(next) => setReadingPrefs({ highlightConflicts: next })}
          />
        </div>
      </section>
    </>
  )
}
