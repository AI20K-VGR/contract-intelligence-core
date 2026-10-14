import { useSyncExternalStore } from 'react'
import { parseStructureView, type StructureView } from './types'

/*
 * Tùy chọn đọc hợp đồng chọn ở Cài đặt, nhớ trên trình duyệt này.
 * openView 'last' = mở đúng kiểu xem dùng lần trước (STRUCTURE_VIEW_KEY).
 */
export type ReadingPrefs = {
  openView: StructureView | 'last'
  autoScroll: boolean
  highlightConflicts: boolean
}

export const READING_PREFS_KEY = 'reading_prefs'

const DEFAULTS: ReadingPrefs = {
  openView: 'last',
  autoScroll: true,
  highlightConflicts: true,
}

function parse(raw: string | null): ReadingPrefs {
  if (!raw) return DEFAULTS
  try {
    const value = JSON.parse(raw) as Partial<
      Record<keyof ReadingPrefs, unknown>
    >
    return {
      openView: parseStructureView(value.openView) ?? 'last',
      autoScroll:
        typeof value.autoScroll === 'boolean'
          ? value.autoScroll
          : DEFAULTS.autoScroll,
      highlightConflicts:
        typeof value.highlightConflicts === 'boolean'
          ? value.highlightConflicts
          : DEFAULTS.highlightConflicts,
    }
  } catch {
    return DEFAULTS
  }
}

function stored(): ReadingPrefs {
  try {
    return parse(window.localStorage.getItem(READING_PREFS_KEY))
  } catch {
    return DEFAULTS
  }
}

let current: ReadingPrefs | null = null
const listeners = new Set<() => void>()

/** Đọc ngoài React (vd. chọn kiểu xem lúc mở trang). */
export function readingPrefs(): ReadingPrefs {
  current ??= stored()
  return current
}

export function setReadingPrefs(patch: Partial<ReadingPrefs>) {
  current = { ...readingPrefs(), ...patch }
  try {
    window.localStorage.setItem(READING_PREFS_KEY, JSON.stringify(current))
  } catch {
    // Không lưu được thì tùy chọn chỉ giữ tới khi tải lại trang.
  }
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  // Đổi ở tab khác thì tab này đổi theo.
  function onStorage(event: StorageEvent) {
    if (event.key !== READING_PREFS_KEY) return
    current = stored()
    listener()
  }
  window.addEventListener('storage', onStorage)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('storage', onStorage)
  }
}

export function useReadingPrefs(): ReadingPrefs {
  return useSyncExternalStore(subscribe, readingPrefs, readingPrefs)
}
