import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

/**
 * Quay về trang trước đó trong app, như nút Back của trình duyệt.
 * Mở thẳng bằng link (chưa có trang trước trong app) thì về `fallback`.
 */
export function useGoBack(fallback: string) {
  const navigate = useNavigate()
  const location = useLocation()
  // React Router đặt key 'default' cho trang đầu tiên của phiên.
  const hasPrevious = location.key !== 'default'
  return useCallback(() => {
    if (hasPrevious) navigate(-1)
    else navigate(fallback, { replace: true })
  }, [fallback, hasPrevious, navigate])
}
