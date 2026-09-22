import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { homePath, validateWorkEmail } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { usePageTitle } from '../hooks/usePageTitle'

export function LoginPage() {
  usePageTitle('Đăng nhập')
  const { user, ready, configured, loginWithSso } = useAuth()
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (ready && user) {
    return <Navigate to={homePath(user.role)} replace />
  }

  async function handleSsoSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setError('')
    setBusy(true)
    try {
      const workEmail = validateWorkEmail(email)
      await loginWithSso(workEmail)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'SSO chưa xác thực được.',
      )
      setBusy(false)
    }
  }

  const locked = busy || !ready

  return (
    <div className="bg-background font-body-md text-on-surface min-h-screen flex flex-col justify-between selection:bg-secondary-container selection:text-on-secondary-fixed relative">
      <div className="fixed inset-0 pointer-events-none bg-grid-pattern opacity-60 z-0" />

      <header className="relative z-10 w-full pt-gutter-lg px-gutter-lg flex items-center justify-between" />

      <main className="relative z-10 flex-1 flex items-center justify-center p-gutter-sm md:p-gutter-lg">
        <div className="flex flex-col w-full items-center justify-center py-gutter-sm">
          <div className="w-full max-w-[420px] mx-auto">
            <div className="bg-surface-container-lowest rounded-lg shadow-sm p-gutter-lg flex flex-col relative overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-1 bg-primary-container" />

              <div className="flex items-center justify-between gap-space-sm mb-space-lg">
                <div className="flex items-center gap-space-xs">
                  <MaterialIcon
                    name="shield"
                    className="text-primary-container text-[18px]"
                  />
                  <span className="font-label-md text-label-md text-primary-container tracking-wider uppercase font-medium">
                    LEXIS CONTRACT INTELLIGENCE
                  </span>
                </div>
              </div>

              <div className="flex flex-col mb-space-md">
                <h1 className="font-headline-md text-headline-md text-primary-container tracking-tight">
                  Đăng nhập
                </h1>
                <p className="font-body-sm text-body-sm text-secondary mt-1">
                  Truy cập không gian làm việc của bạn
                </p>
              </div>

              <ol
                aria-label="Tiến trình đăng nhập"
                className="mb-gutter-sm flex items-center gap-space-sm"
              >
                <li
                  aria-current="step"
                  className="flex items-center gap-space-xs text-primary-container"
                >
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary-container font-label-sm text-label-sm text-on-primary">
                    1
                  </span>
                  <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wider">
                    Email
                  </span>
                </li>
                <li
                  aria-hidden
                  className="h-px min-w-6 flex-1 bg-outline-variant"
                />
                <li className="flex items-center gap-space-xs text-outline">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full border border-outline-variant font-label-sm text-label-sm">
                    2
                  </span>
                  <span className="font-label-sm text-label-sm uppercase tracking-wider">
                    Mật khẩu
                  </span>
                </li>
              </ol>

              <form
                className="flex flex-col gap-space-md"
                onSubmit={(event) => {
                  void handleSsoSubmit(event)
                }}
              >
                <div className="flex flex-col gap-1.5">
                  <label
                    className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant"
                    htmlFor="work-email"
                  >
                    Email doanh nghiệp
                  </label>
                  <div className="relative flex items-center">
                    <input
                      autoComplete="email"
                      className="w-full h-10 px-3 bg-surface-container-low text-on-surface font-body-md text-body-md placeholder:text-outline rounded transition-all focus:bg-surface-container-lowest focus:outline-none focus:ring-2 focus:ring-on-tertiary-container/30 disabled:opacity-70"
                      disabled={locked}
                      id="work-email"
                      placeholder="admin@ci.local"
                      type="email"
                      value={email}
                      onChange={(event) => {
                        setEmail(event.target.value)
                        if (error) setError('')
                      }}
                    />
                    <MaterialIcon
                      name="domain"
                      className="absolute right-3 text-outline text-[18px] pointer-events-none"
                    />
                  </div>
                  <p className="font-label-sm text-label-sm text-outline">
                    Local: admin@ci.local · reviewer@ci.local ·
                    operator@ci.local — mật khẩu nhập trên trang Keycloak.
                  </p>
                </div>

                {!configured ? (
                  <p className="font-body-sm text-body-sm text-error bg-error-container/40 px-space-sm py-space-xs rounded">
                    Chưa cấu hình Keycloak. Thêm VITE_KEYCLOAK_URL,
                    VITE_KEYCLOAK_REALM, VITE_KEYCLOAK_CLIENT_ID vào file
                    .env.local (xem .env.example).
                  </p>
                ) : null}

                {error ? (
                  <p className="font-body-sm text-body-sm text-error bg-error-container/40 px-space-sm py-space-xs rounded">
                    {error}
                  </p>
                ) : null}

                <button
                  className="w-full h-10 bg-primary-container hover:bg-primary text-on-primary font-title-sm text-title-sm rounded transition-all flex items-center justify-center gap-space-xs active:scale-[0.99] shadow-sm disabled:opacity-70"
                  disabled={locked || !configured}
                  type="submit"
                >
                  {busy ? (
                    <>
                      <MaterialIcon
                        name="refresh"
                        className="text-[16px] animate-spin"
                      />
                      <span>Đang chuyển tới SSO…</span>
                    </>
                  ) : (
                    <>
                      <span>Tiếp tục với SSO</span>
                      <MaterialIcon
                        name="arrow_forward"
                        className="text-[16px]"
                      />
                    </>
                  )}
                </button>
              </form>
            </div>
          </div>
        </div>
      </main>

      <footer className="relative z-10 w-full py-gutter-sm px-gutter-lg">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-space-sm text-outline font-label-sm text-label-sm">
          <div className="flex items-center gap-space-md">
            <span>Chính sách bảo mật</span>
            <span className="text-outline-variant">•</span>
            <span>Điều khoản sử dụng</span>
          </div>
          <span className="tracking-wide">
            © 2025 Lexis Contract Intelligence. All rights reserved.
          </span>
        </div>
      </footer>
    </div>
  )
}
