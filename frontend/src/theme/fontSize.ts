import { useSyncExternalStore } from 'react'

/*
 * Cỡ chữ người dùng chọn ở Cài đặt. Cỡ của từng mức nằm trong index.css
 * (:root[data-font-size='…']); ở đây chỉ nhớ lựa chọn và đặt data-font-size
 * lên <html>. Mức "Vừa" là cỡ gốc nên không cần khối CSS riêng.
 */

export type FontSizeId = 'sm' | 'md' | 'lg'

export const FONT_SIZES: { id: FontSizeId; name: string; hint: string }[] = [
  { id: 'sm', name: 'Nhỏ', hint: 'Thấy được nhiều dòng hơn' },
  { id: 'md', name: 'Vừa', hint: 'Cỡ mặc định' },
  { id: 'lg', name: 'Lớn', hint: 'Dễ đọc hợp đồng dài' },
]

export const DEFAULT_FONT_SIZE: FontSizeId = 'md'
export const FONT_SIZE_KEY = 'theme_font_size'

function parseFontSize(raw: unknown): FontSizeId | null {
  return FONT_SIZES.some((size) => size.id === raw) ? (raw as FontSizeId) : null
}

function storedFontSize(): FontSizeId {
  try {
    return (
      parseFontSize(window.localStorage.getItem(FONT_SIZE_KEY)) ??
      DEFAULT_FONT_SIZE
    )
  } catch {
    return DEFAULT_FONT_SIZE
  }
}

let current: FontSizeId = DEFAULT_FONT_SIZE
const listeners = new Set<() => void>()

function apply(id: FontSizeId) {
  current = id
  document.documentElement.dataset.fontSize = id
  for (const listener of listeners) listener()
}

/** Gọi một lần trước khi render để không nháy cỡ chữ mặc định. */
export function initFontSize() {
  apply(storedFontSize())
  // Đổi ở tab khác thì tab này đổi theo.
  window.addEventListener('storage', (event) => {
    if (event.key === FONT_SIZE_KEY) apply(storedFontSize())
  })
}

export function setFontSize(id: FontSizeId) {
  apply(id)
  try {
    window.localStorage.setItem(FONT_SIZE_KEY, id)
  } catch {
    // Không lưu được thì cỡ chữ chỉ giữ tới khi tải lại trang.
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useFontSize(): FontSizeId {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => current,
  )
}
