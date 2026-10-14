import { FONT_SIZES, setFontSize, useFontSize } from '../theme/fontSize'
import { MaterialIcon } from './icons'

/* Chữ "Aa" mỗi thẻ theo đúng tỉ lệ của mức đó, không theo cỡ đang chọn. */
const sampleSize = { sm: 'text-[18px]', md: 'text-[22px]', lg: 'text-[26px]' }

export function FontSizePicker() {
  const current = useFontSize()

  return (
    <section className="bg-surface-container-lowest rounded-xl shadow-sm px-space-lg py-space-lg flex flex-col gap-space-md">
      <div className="flex flex-col gap-space-xs">
        <h2 className="font-title-sm text-title-sm text-on-surface">Cỡ chữ</h2>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Áp dụng cho chữ trên mọi trang, kể cả nội dung hợp đồng. Được nhớ trên
          trình duyệt này.
        </p>
      </div>

      <div
        aria-label="Cỡ chữ"
        className="grid grid-cols-1 gap-space-md sm:grid-cols-3"
        role="radiogroup"
      >
        {FONT_SIZES.map((size) => {
          const active = size.id === current
          return (
            <button
              key={size.id}
              aria-checked={active}
              className={`group flex items-center gap-space-md rounded-lg border bg-surface-container-lowest p-space-md text-left transition-all ${
                active
                  ? 'border-brand-600 ring-2 ring-brand-600/30'
                  : 'border-outline-variant/60 hover:border-outline hover:shadow-sm'
              }`}
              role="radio"
              type="button"
              onClick={() => setFontSize(size.id)}
            >
              <span
                aria-hidden="true"
                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-brand-50 font-semibold text-brand-700 ${sampleSize[size.id]}`}
              >
                Aa
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="font-body-md text-body-md font-semibold text-on-surface">
                  {size.name}
                </span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">
                  {size.hint}
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
        })}
      </div>

      <p className="rounded-lg bg-tone-50 px-space-md py-space-sm font-body-md text-body-md text-on-surface">
        Bên B có trách nhiệm thanh toán toàn bộ giá trị hợp đồng trong vòng 30
        ngày kể từ ngày nhận được hóa đơn hợp lệ.
      </p>
    </section>
  )
}
