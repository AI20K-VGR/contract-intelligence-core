import { useSyncExternalStore } from 'react'
import {
  buildPalette,
  DEFAULT_THEME_COLOR,
  normalizeHue,
  paletteVariables,
} from './palette'

/*
 * Màu giao diện người dùng chọn ở Cài đặt. Nhớ theo trình duyệt (localStorage),
 * ghi biến CSS lên <html> nên sidebar, header và các trang theme-soft đổi ngay.
 */

export const THEME_COLOR_KEY = 'theme_color'

export function parseThemeColor(raw: unknown): number | null {
  if (typeof raw !== 'string' || raw.trim() === '') return null
  const hue = Number(raw)
  return Number.isFinite(hue) ? normalizeHue(hue) : null
}

function storedThemeColor(): number {
  try {
    return (
      parseThemeColor(window.localStorage.getItem(THEME_COLOR_KEY)) ??
      DEFAULT_THEME_COLOR
    )
  } catch {
    return DEFAULT_THEME_COLOR
  }
}

let current = DEFAULT_THEME_COLOR
const listeners = new Set<() => void>()

function apply(choice: number) {
  current = choice
  const style = document.documentElement.style
  for (const [name, value] of Object.entries(
    paletteVariables(buildPalette(choice)),
  )) {
    style.setProperty(name, value)
  }
  for (const listener of listeners) listener()
}

/** Gọi một lần trước khi render để không nháy màu mặc định. */
export function initThemeColor() {
  apply(storedThemeColor())
  // Đổi màu ở tab khác thì tab này đổi theo.
  window.addEventListener('storage', (event) => {
    if (event.key === THEME_COLOR_KEY) apply(storedThemeColor())
  })
}

export function setThemeColor(choice: number) {
  apply(choice)
  try {
    window.localStorage.setItem(THEME_COLOR_KEY, String(choice))
  } catch {
    // Không lưu được thì màu chỉ giữ tới khi tải lại trang.
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useThemeColor(): number {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => current,
  )
}
