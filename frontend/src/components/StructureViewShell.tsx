import type { ReactNode } from 'react'
import type { BranchTone } from '../structure/display'
import { MaterialIcon } from './icons'

/** Khung + header thống nhất cho các kiểu xem cấu trúc (dàn bài, văn bản, trang). */
export function ViewShell({
  icon,
  title,
  caption,
  controls,
  children,
}: {
  icon: string
  title: string
  caption?: string
  controls?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-outline-variant/20 bg-surface-container-lowest shadow-sm">
      <div className="z-10 flex items-center justify-between gap-3 border-b border-outline-variant/20 bg-surface-container-low/60 px-4 py-2">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex min-w-0 items-center gap-2 font-title-sm text-title-sm text-primary">
            <MaterialIcon
              name={icon}
              className="shrink-0 text-[20px] text-primary"
            />
            <span className="truncate font-semibold">{title}</span>
          </div>
          {caption ? (
            <span
              className="hidden shrink-0 bg-surface-container px-2.5 py-0.5 font-mono text-[11px] text-secondary xl:inline"
              style={{ borderRadius: '9999px' }}
            >
              {caption}
            </span>
          ) : null}
        </div>
        {controls ? (
          <div className="flex shrink-0 items-center gap-0.5">{controls}</div>
        ) : null}
      </div>
      {children}
    </div>
  )
}

export function IconButton({
  icon,
  label,
  square,
  active,
  onClick,
}: {
  icon: string
  label: string
  square?: boolean
  active?: boolean
  onClick: () => void
}) {
  return (
    <button
      aria-label={label}
      aria-pressed={active}
      className={`flex items-center justify-center transition-colors ${
        square ? 'h-9 w-9' : 'h-8 w-8 rounded-full'
      } ${
        active
          ? 'bg-primary text-white hover:bg-primary-container'
          : 'text-slate-600 hover:bg-slate-200/70 hover:text-slate-900'
      }`}
      title={label}
      type="button"
      onClick={onClick}
    >
      <MaterialIcon name={icon} className="text-[20px]" />
    </button>
  )
}

export function HeaderDivider() {
  return <span className="mx-1 h-4 w-px bg-outline-variant/40" />
}

/** Ô lọc nhanh nằm trong header. */
export function FilterField({
  value,
  placeholder,
  onChange,
}: {
  value: string
  placeholder: string
  onChange: (next: string) => void
}) {
  return (
    <label className="relative mr-1 hidden items-center sm:flex">
      <MaterialIcon
        name="search"
        className="pointer-events-none absolute left-2 text-[16px] text-outline"
      />
      <input
        aria-label={placeholder}
        className="h-8 w-52 rounded-full border border-outline-variant/40 bg-surface-container-lowest pl-7 pr-7 text-[12px] text-on-surface placeholder:text-outline focus:outline-none focus:ring-1 focus:ring-secondary"
        placeholder={placeholder}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      {value ? (
        <button
          aria-label="Xoá lọc"
          className="absolute right-1.5 flex h-5 w-5 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200"
          type="button"
          onClick={() => onChange('')}
        >
          <MaterialIcon name="close" className="text-[14px]" />
        </button>
      ) : null}
    </label>
  )
}

/** Số trích dẫn nhỏ, viền màu nhánh. */
export function CiteBadge({
  n,
  tone,
  active,
  onClick,
}: {
  n: number | undefined
  tone: BranchTone
  active?: boolean
  onClick?: () => void
}) {
  if (!n) return null
  const className = `inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded-full border px-1 text-[10px] font-semibold leading-none ${
    active ? 'text-white' : 'bg-white text-slate-800'
  }`
  const style = {
    borderColor: tone.line,
    backgroundColor: active ? tone.line : undefined,
  }
  if (!onClick) {
    return (
      <span className={className} style={style}>
        {n}
      </span>
    )
  }
  return (
    <button
      className={`${className} hover:shadow-sm`}
      title={`Trích dẫn [${n}]`}
      type="button"
      onClick={(event) => {
        event.stopPropagation()
        onClick()
      }}
    >
      {n}
    </button>
  )
}

export function AttentionStar({ size = 15 }: { size?: number }) {
  return (
    <span
      className="flex shrink-0 items-center justify-center overflow-hidden text-amber-500"
      style={{ width: size + 1, height: size + 3, fontSize: size }}
      title="Có chỗ cần kiểm tra"
    >
      <MaterialIcon name="star" style={{ fontSize: size }} />
    </span>
  )
}

/** Tô đậm đoạn khớp bộ lọc. */
export function Highlight({ text, query }: { text: string; query: string }) {
  const needle = query.trim().toLowerCase()
  if (!needle) return <>{text}</>
  const at = text.toLowerCase().indexOf(needle)
  if (at < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, at)}
      <mark className="rounded-sm bg-amber-200/80 px-0.5 text-inherit">
        {text.slice(at, at + needle.length)}
      </mark>
      {text.slice(at + needle.length)}
    </>
  )
}

export function EmptyStructure() {
  return (
    <div className="flex h-full min-h-48 items-center rounded-xl bg-surface-container-lowest px-6 shadow-sm">
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        OCR đã xong, nhưng tài liệu chưa có nút cấu trúc.
      </p>
    </div>
  )
}
