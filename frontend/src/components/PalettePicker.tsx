import { PALETTES, setPalette, usePalette } from '../theme/palettes'
import { MaterialIcon } from './icons'

/*
 * Mỗi thẻ là một giao diện thu nhỏ đặt data-palette riêng, nên tự lấy màu
 * thật của bộ đó (thanh menu, nút chính, nền trang) thay vì dải màu thô.
 */
function PalettePreview({ id }: { id: string }) {
  return (
    <span
      aria-hidden="true"
      className="flex h-24 overflow-hidden rounded-md border border-outline-variant/60"
      data-palette={id}
    >
      <span className="flex w-1/4 flex-col gap-1.5 bg-side p-2">
        <span className="h-2.5 w-2.5 rounded-sm bg-side-logo" />
        <span className="mt-1 h-2 rounded-sm bg-side-active" />
        <span className="h-1.5 w-3/4 rounded-sm bg-side-chip" />
        <span className="h-1.5 w-2/3 rounded-sm bg-side-chip" />
      </span>
      <span className="flex flex-1 flex-col gap-1.5 bg-tone-50 p-2">
        <span className="h-2 w-1/2 rounded-sm bg-tone-300" />
        <span className="flex flex-1 flex-col gap-1.5 rounded bg-white p-1.5 shadow-sm">
          <span className="h-1.5 w-4/5 rounded-sm bg-tone-200" />
          <span className="h-1.5 w-3/5 rounded-sm bg-tone-200" />
          <span className="mt-auto flex items-center gap-1">
            <span className="h-2.5 w-8 rounded-sm bg-brand-600" />
            <span className="h-2.5 w-5 rounded-sm bg-brand-100" />
            <span className="ml-auto h-2.5 w-2.5 rounded-full bg-blush-100" />
          </span>
        </span>
      </span>
    </span>
  )
}

export function PalettePicker() {
  const current = usePalette()

  return (
    <section className="bg-surface-container-lowest rounded-xl shadow-sm px-space-lg py-space-lg flex flex-col gap-space-md">
      <div className="flex flex-col gap-space-xs">
        <h2 className="font-title-sm text-title-sm text-on-surface">
          Bộ màu giao diện
        </h2>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Giao diện đổi ngay khi chọn và được nhớ trên trình duyệt này.
        </p>
      </div>

      <div
        aria-label="Bộ màu"
        className="grid grid-cols-1 gap-space-md sm:grid-cols-2 lg:grid-cols-3"
        role="radiogroup"
      >
        {PALETTES.map((palette) => {
          const active = palette.id === current
          return (
            <button
              key={palette.id}
              aria-checked={active}
              className={`group flex flex-col gap-space-sm rounded-lg border bg-surface-container-lowest p-space-sm text-left transition-all ${
                active
                  ? 'border-brand-600 ring-2 ring-brand-600/30'
                  : 'border-outline-variant/60 hover:border-outline hover:shadow-sm'
              }`}
              role="radio"
              type="button"
              onClick={() => setPalette(palette.id)}
            >
              <PalettePreview id={palette.id} />
              <span className="flex items-center gap-space-sm px-0.5">
                <span className="flex -space-x-1">
                  {palette.swatches.map((color) => (
                    <span
                      key={color}
                      className="h-3.5 w-3.5 rounded-full shadow-[inset_0_0_0_1px_rgb(0_0_0/0.12)] ring-2 ring-surface-container-lowest"
                      style={{ background: color }}
                    />
                  ))}
                </span>
                <span className="flex-1 truncate font-body-sm text-body-sm font-semibold text-on-surface">
                  {palette.name}
                </span>
                <MaterialIcon
                  name={active ? 'check_circle' : 'radio_button_unchecked'}
                  className={`text-[18px] ${
                    active
                      ? 'text-brand-600'
                      : 'text-outline-variant group-hover:text-outline'
                  }`}
                />
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
