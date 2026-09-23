import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { homePath } from '../auth/session'
import { MaterialIcon } from '../components/icons'
import { usePageTitle } from '../hooks/usePageTitle'

export function AuthCallbackPage() {
  usePageTitle('Đang đăng nhập SSO')
  const navigate = useNavigate()
  const { completeSsoCallback } = useAuth()
  const [error, setError] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const ssoError = params.get('error_description') || params.get('error')
    if (ssoError) {
      setError(ssoError)
      return
    }

    let active = true

    void completeSsoCallback()
      .then((session) => {
        if (active) {
          navigate(homePath(session.role), { replace: true })
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(
            cause instanceof Error
              ? cause.message
              : 'Không hoàn tất đăng nhập SSO.',
          )
        }
      })

    return () => {
      active = false
    }
  }, [completeSsoCallback, navigate])

  return (
    <div className="bg-background font-body-md text-on-surface min-h-screen flex items-center justify-center p-gutter-lg">
      <div className="w-full max-w-[420px] bg-surface-container-lowest rounded-lg shadow-sm p-gutter-lg flex flex-col gap-space-md">
        {error ? (
          <>
            <h1 className="font-headline-md text-headline-md text-primary-container">
              Đăng nhập SSO thất bại
            </h1>
            <p className="font-body-sm text-body-sm text-error bg-error-container/40 px-space-sm py-space-xs rounded">
              {error}
            </p>
            <button
              className="w-full h-10 bg-primary-container hover:bg-primary text-on-primary font-title-sm text-title-sm rounded"
              type="button"
              onClick={() => navigate('/', { replace: true })}
            >
              Quay lại đăng nhập
            </button>
          </>
        ) : (
          <div className="flex items-center gap-space-sm text-secondary">
            <MaterialIcon
              name="progress_activity"
              className="text-[20px] animate-spin"
            />
            <span>Đang hoàn tất đăng nhập SSO…</span>
          </div>
        )}
      </div>
    </div>
  )
}
