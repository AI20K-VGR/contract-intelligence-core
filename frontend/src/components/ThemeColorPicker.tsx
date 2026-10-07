import { DEFAULT_THEME_COLOR, swatchColor } from '../theme/palette'
import { setThemeColor, useThemeColor } from '../theme/themeColor'

const RAINBOW = `linear-gradient(to right, ${Array.from(
  { length: 25 },
  (_, i) => `${swatchColor(i * 15)} ${((i * 15) / 360) * 100}%`,
).join(', ')})`

// Tên màu gần nhất, để trình đọc màn hình đọc "Vàng" thay vì "95".
const HUE_NAMES: [number, string][] = [
  [25, 'Đỏ'],
  [50, 'Cam'],
  [95, 'Vàng'],
  [150, 'Xanh lá'],
  [185, 'Xanh ngọc'],
  [262, 'Xanh dương'],
  [295, 'Tím'],
  [350, 'Hồng'],
]

function hueName(hue: number) {
  const distance = (other: number) => {
    const gap = Math.abs(other - hue)
    return Math.min(gap, 360 - gap)
  }
  return HUE_NAMES.reduce((best, entry) =>
    distance(entry[0]) < distance(best[0]) ? entry : best,
  )[1]
}

export function ThemeColorPicker() {
  const hue = useThemeColor()

  return (
    <section className="bg-surface-container-lowest rounded-xl shadow-sm px-space-lg py-space-lg flex flex-col gap-space-lg">
      <div className="flex items-start justify-between gap-space-md">
        <div className="flex flex-col gap-space-xs">
          <h2 className="font-title-sm text-title-sm text-on-surface">
            Màu giao diện
          </h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Kéo thanh màu để chọn màu chủ đạo. Giao diện đổi ngay và được nhớ
            trên trình duyệt này.
          </p>
        </div>
        <button
          className="shrink-0 px-space-md py-1.5 rounded-lg border border-outline-variant font-label-md text-label-md text-on-surface hover:bg-surface-container transition-colors disabled:opacity-50 disabled:hover:bg-transparent"
          disabled={hue === DEFAULT_THEME_COLOR}
          type="button"
          onClick={() => setThemeColor(DEFAULT_THEME_COLOR)}
        >
          Về mặc định
        </button>
      </div>

      <input
        aria-label="Màu chủ đạo"
        aria-valuetext={hueName(hue)}
        className="hue-slider w-full"
        max={359}
        min={0}
        step={1}
        style={{ background: RAINBOW }}
        type="range"
        value={hue}
        onChange={(event) => setThemeColor(Number(event.target.value))}
      />
    </section>
  )
}
