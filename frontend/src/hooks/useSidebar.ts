import { createContext, useContext, useEffect, useRef } from 'react'

/** Thanh menu bên trái: thu gọn (chỉ còn icon) hay mở đầy đủ. */
export type SidebarState = {
  collapsed: boolean
  setCollapsed: (collapsed: boolean) => void
}

export const SidebarContext = createContext<SidebarState>({
  collapsed: false,
  setCollapsed: () => {},
})

export function useSidebar() {
  return useContext(SidebarContext)
}

/**
 * Trang cần chỗ (vd. mở khung PDF bên cạnh) thì thu gọn menu; hết cần thì trả
 * menu về như trước khi thu.
 */
export function useCompactSidebar(active: boolean) {
  const { collapsed, setCollapsed } = useSidebar()
  const before = useRef(collapsed)
  const latest = useRef(collapsed)
  latest.current = collapsed

  useEffect(() => {
    if (!active) return
    before.current = latest.current
    setCollapsed(true)
    return () => setCollapsed(before.current)
  }, [active, setCollapsed])
}
