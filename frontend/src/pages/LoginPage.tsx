import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { homePath, type AppRole } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { GoogleIcon, MaterialIcon } from '../components/icons'
import { usePageTitle } from '../hooks/usePageTitle'

type LoginBusy = 'idle' | 'google' | 'sso' | 'admin' | 'user'

export function LoginPage() {
  usePageTitle('Đăng nhập')
  const navigate = useNavigate()
  const { loginAs, loginWithEmail } = useAuth()
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<LoginBusy>('idle')

  async function finishLogin(role: AppRole) {
    navigate(homePath(role))
  }

  async function handleQuickLogin(role: AppRole) {
    if (busy !== 'idle') return
    setError('')
    setBusy(role)
    try {
      const user = await loginAs(role)
      await finishLogin(user.role)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không đăng nhập được.')
    } finally {
      setBusy('idle')
    }
  }

  async function handleGoogleContinue() {
    if (busy !== 'idle') return
    setError('')
    setBusy('google')
    try {
      const user = email.trim()
        ? await loginWithEmail(email)
        : await loginAs('admin')
      await finishLogin(user.role)
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Google Workspace chưa xác thực được tài khoản.',
      )
    } finally {
      setBusy('idle')
    }
  }

  async function handleSsoSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy !== 'idle') return
    setError('')
    setBusy('sso')
    try {
      const user = await loginWithEmail(email)
      await finishLogin(user.role)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'SSO chưa xác thực được.',
      )
    } finally {
      setBusy('idle')
    }
  }

  const locked = busy !== 'idle'

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

              <div className="flex flex-col mb-gutter-sm">
                <h1 className="font-headline-md text-headline-md text-primary-container tracking-tight">
                  Đăng nhập
                </h1>
                <p className="font-body-sm text-body-sm text-secondary mt-1">
                  Truy cập không gian làm việc của bạn
                </p>
              </div>

              <div className="flex flex-col gap-space-md">
                <button
                  className="w-full bg-surface-container-lowest hover:bg-surface-container-low text-on-secondary-fixed font-title-sm text-title-sm py-3 px-4 rounded transition-colors shadow-sm flex items-center justify-center gap-space-md group disabled:opacity-70"
                  disabled={locked}
                  type="button"
                  onClick={() => {
                    void handleGoogleContinue()
                  }}
                >
                  <GoogleIcon />
                  <span className="tracking-normal font-medium">
                    {busy === 'google'
                      ? 'Đang xác thực Google…'
                      : 'Tiếp tục với Google Workspace'}
                  </span>
                </button>

                <div className="relative flex items-center justify-center my-space-xs">
                  <div className="w-full bg-surface-container-high h-[1px]" />
                  <span className="absolute bg-surface-container-lowest px-space-sm font-label-sm text-label-sm text-outline uppercase tracking-wider">
                    hoặc
                  </span>
                </div>

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
                        placeholder="ten@apexlaw.vn"
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
                      Demo: cuong.nguyen@apexlaw.vn (Admin) ·
                      mai.tran@apexlaw.vn (User)
                    </p>
                  </div>

                  {error ? (
                    <p className="font-body-sm text-body-sm text-error bg-error-container/40 px-space-sm py-space-xs rounded">
                      {error}
                    </p>
                  ) : null}

                  <button
                    className="w-full h-10 bg-primary-container hover:bg-primary text-on-primary font-title-sm text-title-sm rounded transition-all flex items-center justify-center gap-space-xs active:scale-[0.99] shadow-sm disabled:opacity-70"
                    disabled={locked}
                    type="submit"
                  >
                    {busy === 'sso' ? (
                      <>
                        <MaterialIcon
                          name="refresh"
                          className="text-[16px] animate-spin"
                        />
                        <span>Đang xác thực SSO…</span>
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

                <div className="relative flex items-center justify-center my-space-xs">
                  <div className="w-full bg-surface-container-high h-[1px]" />
                  <span className="absolute bg-surface-container-lowest px-space-sm font-label-sm text-label-sm text-outline uppercase tracking-wider">
                    đăng nhập nhanh
                  </span>
                </div>

                <div className="flex flex-col gap-space-sm">
                  <button
                    className="w-full h-10 px-space-sm bg-primary-container hover:bg-primary text-on-primary font-title-sm text-title-sm rounded transition-all flex items-center justify-center gap-space-xs active:scale-[0.99] shadow-sm disabled:opacity-70"
                    disabled={locked}
                    type="button"
                    onClick={() => {
                      void handleQuickLogin('admin')
                    }}
                  >
                    <MaterialIcon
                      name="admin_panel_settings"
                      className="text-[16px]"
                    />
                    <span>
                      {busy === 'admin'
                        ? 'Đang vào Admin…'
                        : 'Đăng nhập với Admin'}
                    </span>
                  </button>
                  <button
                    className="w-full h-10 px-space-sm bg-surface-container-lowest hover:bg-surface-container-low text-on-secondary-fixed font-title-sm text-title-sm rounded transition-colors shadow-sm flex items-center justify-center gap-space-xs disabled:opacity-70"
                    disabled={locked}
                    type="button"
                    onClick={() => {
                      void handleQuickLogin('user')
                    }}
                  >
                    <MaterialIcon name="person" className="text-[16px]" />
                    <span>
                      {busy === 'user'
                        ? 'Đang vào User…'
                        : 'Đăng nhập với User'}
                    </span>
                  </button>
                </div>

                <div className="pt-space-xs text-center">
                  <p className="font-label-sm text-label-sm text-secondary">
                    Trợ giúp? Dùng email demo Apex Law hoặc nút đăng nhập nhanh.
                  </p>
                </div>
              </div>
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
