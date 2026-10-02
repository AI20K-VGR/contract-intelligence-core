import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { openMonitoringSession } from '../api/monitoring'
import { MaterialIcon } from '../components/icons'
import { usePageTitle } from '../hooks/usePageTitle'
import { ForbiddenPage } from './ForbiddenPage'

const TITLE = 'Giám sát hệ thống'

type SessionState =
  | { kind: 'loading' }
  | { kind: 'ready'; url: string; notice: string | null }
  | { kind: 'forbidden' }
  | { kind: 'error'; message: string }

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Phiên đăng nhập đã hết hạn. Đăng nhập lại để xem giám sát.'
    }
    if (error.status === 503) {
      return 'Hệ thống giám sát chưa được cấu hình trên backend.'
    }
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được backend.'
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Không mở được bảng giám sát. Thử lại.'
}

/**
 * Grafana dashboard inside the app shell. The route is wrapped in
 * RequireRole(admin); the backend checks ADMINISTRATOR again on the session
 * call and on every /grafana request, so hiding the menu is not the guard.
 */
export function MonitoringPage() {
  const [state, setState] = useState<SessionState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let renewTimer: number | undefined

    async function open(first: boolean) {
      try {
        const session = await openMonitoringSession(controller.signal)
        if (first) {
          setState({ kind: 'ready', url: session.dashboardUrl, notice: null })
        } else {
          setState((current) =>
            current.kind === 'ready' ? { ...current, notice: null } : current,
          )
        }
        // Renew the short-lived /grafana cookie halfway through its life,
        // with a fresh Keycloak token (a removed admin role stops it here).
        renewTimer = window.setTimeout(
          () => void open(false),
          (session.expiresIn * 1000) / 2,
        )
      } catch (error) {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 403) {
          setState({ kind: 'forbidden' })
          return
        }
        const message = errorMessage(error)
        setState((current) =>
          first || current.kind !== 'ready'
            ? { kind: 'error', message }
            : { ...current, notice: message },
        )
      }
    }

    void open(true)
    return () => {
      controller.abort()
      window.clearTimeout(renewTimer)
    }
  }, [attempt])

  if (state.kind === 'forbidden') {
    return <ForbiddenPage />
  }
  return (
    <MonitoringView
      state={state}
      onRetry={() => {
        setState({ kind: 'loading' })
        setAttempt((n) => n + 1)
      }}
    />
  )
}

function MonitoringView({
  state,
  onRetry,
}: {
  state: Exclude<SessionState, { kind: 'forbidden' }>
  onRetry: () => void
}) {
  usePageTitle(TITLE)
  const [frameKey, setFrameKey] = useState(0)

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-space-sm pt-space-md">
      <div className="flex items-center justify-between gap-space-md">
        <p className="flex items-center gap-space-xs font-body-sm text-body-sm text-secondary">
          <MaterialIcon name="monitoring" className="text-[18px]" />
          Hệ thống, Docker, OCR, chi phí và trạng thái dịch vụ — Grafana (chỉ
          xem). Trace chi tiết từng tài liệu nằm ở Langfuse.
        </p>
        <button
          className="flex items-center gap-space-xs px-space-md py-1 rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm transition-colors disabled:text-outline disabled:cursor-not-allowed"
          type="button"
          disabled={state.kind === 'loading'}
          onClick={() =>
            state.kind === 'ready' ? setFrameKey((n) => n + 1) : onRetry()
          }
        >
          <MaterialIcon name="refresh" className="text-[16px]" />
          Tải lại
        </button>
      </div>

      {state.kind === 'ready' && state.notice ? (
        <div
          role="alert"
          className="px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm"
        >
          {state.notice}
        </div>
      ) : null}

      {state.kind === 'loading' ? (
        <div className="flex flex-1 items-center justify-center rounded-xl bg-surface-container-lowest shadow-sm font-body-sm text-body-sm text-secondary">
          Đang mở bảng giám sát…
        </div>
      ) : null}

      {state.kind === 'error' ? (
        <div
          role="alert"
          className="px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm"
        >
          {state.message}
        </div>
      ) : null}

      {state.kind === 'ready' ? (
        <iframe
          key={frameKey}
          title="Grafana — giám sát hệ thống"
          src={state.url}
          className="min-h-0 w-full flex-1 rounded-xl border-0 bg-surface-container-lowest shadow-sm"
          // No top-navigation: the dashboard can never redirect the app.
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          referrerPolicy="no-referrer"
        />
      ) : null}
    </div>
  )
}
