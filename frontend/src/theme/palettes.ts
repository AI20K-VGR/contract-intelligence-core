import { useSyncExternalStore } from 'react'

/*
 * Bộ màu giao diện người dùng chọn ở Cài đặt. Màu của từng bộ nằm trong
 * index.css (:root[data-palette='…']); ở đây chỉ nhớ lựa chọn và đặt
 * data-palette lên <html>.
 */

export type PaletteId = '2' | '3' | '4' | '5' | '7' | '8' | '9'

export const PALETTES: { id: PaletteId; name: string; swatches: string[] }[] = [
  {
    id: '2',
    name: 'Bãi biển',
    swatches: ['#89aeb2', '#97f2f3', '#f1e0b0', '#f1cdb0', '#e7cfc8'],
  },
  {
    id: '3',
    name: 'Mận chín',
    swatches: ['#4f4762', '#efdecd', '#ffadb5', '#d63a6f'],
  },
  {
    id: '4',
    name: 'Xanh công nghệ',
    swatches: ['#1e3a5f', '#1e88ff', '#e6e6e6', '#f2f2f2'],
  },
  {
    id: '5',
    name: 'Vườn hè',
    swatches: ['#b9e5a6', '#e6c27a', '#ef9d7a', '#e98aa6'],
  },
  {
    id: '7',
    name: 'Bạc hà',
    swatches: ['#addfd0', '#f1a6a3', '#a98aa8', '#eaf6f4'],
  },
  {
    id: '8',
    name: 'Hoàng hôn',
    swatches: ['#fdf6e3', '#b7dcd9', '#f7a46b', '#fdc39c'],
  },
  {
    id: '9',
    name: 'Rừng nhiệt đới',
    swatches: ['#4ba89a', '#b5e2c0', '#f2edcc', '#f2c6c8'],
  },
]

export const DEFAULT_PALETTE: PaletteId = '2'
export const PALETTE_KEY = 'theme_palette'

export function parsePalette(raw: unknown): PaletteId | null {
  return PALETTES.some((palette) => palette.id === raw)
    ? (raw as PaletteId)
    : null
}

function storedPalette(): PaletteId {
  try {
    return (
      parsePalette(window.localStorage.getItem(PALETTE_KEY)) ?? DEFAULT_PALETTE
    )
  } catch {
    return DEFAULT_PALETTE
  }
}

let current: PaletteId = DEFAULT_PALETTE
const listeners = new Set<() => void>()

function apply(id: PaletteId) {
  current = id
  document.documentElement.dataset.palette = id
  for (const listener of listeners) listener()
}

/** Gọi một lần trước khi render để không nháy bộ màu mặc định. */
export function initPalette() {
  apply(storedPalette())
  // Đổi ở tab khác thì tab này đổi theo.
  window.addEventListener('storage', (event) => {
    if (event.key === PALETTE_KEY) apply(storedPalette())
  })
}

export function setPalette(id: PaletteId) {
  apply(id)
  try {
    window.localStorage.setItem(PALETTE_KEY, id)
  } catch {
    // Không lưu được thì bộ màu chỉ giữ tới khi tải lại trang.
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function usePalette(): PaletteId {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => current,
  )
}
