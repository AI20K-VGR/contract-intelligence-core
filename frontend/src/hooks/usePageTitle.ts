import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

const PageTitleContext = createContext('')
const SetPageTitleContext = createContext<(title: string) => void>(() => {})
const HeaderShowsTitleContext = createContext(false)

export function PageTitleProvider({ children }: { children: ReactNode }) {
  const [title, setTitle] = useState('')
  return createElement(
    HeaderShowsTitleContext.Provider,
    { value: true },
    createElement(
      SetPageTitleContext.Provider,
      { value: setTitle },
      createElement(PageTitleContext.Provider, { value: title }, children),
    ),
  )
}

export function useHeaderShowsPageTitle() {
  return useContext(HeaderShowsTitleContext)
}

export function useCurrentPageTitle() {
  return useContext(PageTitleContext)
}

export function usePageTitle(title: string) {
  const setTitle = useContext(SetPageTitleContext)
  useEffect(() => {
    document.title = `${title} · Lexis Contract Intelligence`
    setTitle(title)
  }, [setTitle, title])
}
