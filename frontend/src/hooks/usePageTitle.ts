import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

/** Một mục trên đường dẫn ở header; mục cuối là trang đang xem. */
export type Crumb = { label: string; to?: string }

const PageTitleContext = createContext('')
const SetPageTitleContext = createContext<(title: string) => void>(() => {})
const BreadcrumbContext = createContext<Crumb[] | null>(null)
const SetBreadcrumbContext = createContext<(crumbs: Crumb[] | null) => void>(
  () => {},
)
const HeaderShowsTitleContext = createContext(false)

export function PageTitleProvider({ children }: { children: ReactNode }) {
  const [title, setTitle] = useState('')
  const [crumbs, setCrumbs] = useState<Crumb[] | null>(null)
  return createElement(
    HeaderShowsTitleContext.Provider,
    { value: true },
    createElement(
      SetPageTitleContext.Provider,
      { value: setTitle },
      createElement(
        SetBreadcrumbContext.Provider,
        { value: setCrumbs },
        createElement(
          BreadcrumbContext.Provider,
          { value: crumbs },
          createElement(PageTitleContext.Provider, { value: title }, children),
        ),
      ),
    ),
  )
}

export function useHeaderShowsPageTitle() {
  return useContext(HeaderShowsTitleContext)
}

export function useCurrentPageTitle() {
  return useContext(PageTitleContext)
}

export function useCurrentBreadcrumb() {
  return useContext(BreadcrumbContext)
}

export function usePageTitle(title: string) {
  const setTitle = useContext(SetPageTitleContext)
  useEffect(() => {
    document.title = `${title} · Lexis Contract Intelligence`
    setTitle(title)
  }, [setTitle, title])
}

/**
 * Header hiện đường dẫn này thay cho tiêu đề, vd. Hồ sơ › abc › Cấu trúc cây.
 * Rời trang thì header về lại tiêu đề.
 */
export function usePageBreadcrumb(crumbs: Crumb[]) {
  const setCrumbs = useContext(SetBreadcrumbContext)
  // So theo nội dung: mảng mới sau mỗi lần render không làm effect chạy lại.
  const key = JSON.stringify(crumbs)
  useEffect(() => {
    setCrumbs(JSON.parse(key) as Crumb[])
    return () => setCrumbs(null)
  }, [setCrumbs, key])
}
