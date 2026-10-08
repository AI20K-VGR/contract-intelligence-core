import { PALETTES, setPalette, usePalette } from '../theme/palettes'
import { MaterialIcon } from './icons'

export function PalettePicker() {
  const current = usePalette()

  return (
    <section className="bg-surface-container-lowest rounded-xl shadow-sm px-space-lg py-space-lg flex flex-col gap-space-md">
      <div className="flex flex-col gap-space-xs">
        <h2 className="font-title-sm text-title-sm text-on-surface">
          Bộ màu giao diện
        </h2>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Chọn một bộ màu. Giao diện đổi ngay và được nhớ trên trình duyệt này.
        </p>
      </div>

      <div
        aria-label="Bộ màu"
        className="grid grid-cols-1 gap-space-sm sm:grid-cols-2 lg:grid-cols-3"
        role="radiogroup"
      >
        {PALETTES.map((palette, index) => {
          const active = palette.id === current
          return (
            <button
              key={palette.id}
              aria-checked={active}
              className={`flex flex-col gap-space-sm rounded-lg border p-space-sm text-left transition-colors ${
                active
                  ? 'border-brand-600 ring-1 ring-brand-600'
                  : 'border-outline-variant hover:border-outline'
              }`}
              role="radio"
              type="button"
              onClick={() => setPalette(palette.id)}
            >
              <span className="flex h-10 overflow-hidden rounded-md">
                {palette.swatches.map((color) => (
                  <span
                    key={color}
                    className="flex-1"
                    style={{ background: color }}
                  />
                ))}
              </span>
              <span className="flex items-center justify-between font-body-sm text-body-sm font-semibold text-on-surface">
                {index + 1}. {palette.name}
                {active ? (
                  <MaterialIcon
                    name="check_circle"
                    className="text-[18px] text-brand-600"
                  />
                ) : null}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
