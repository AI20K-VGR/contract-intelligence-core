import { useEffect, useState } from 'react'
import { getUserManager } from './oidc'
import {
  SESSION_EXPIRED_EVENT,
  SESSION_EXPIRED_MESSAGE,
} from './sessionExpired'

export function SessionExpiredDialog() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onEvent = () => {
      setOpen(true)
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, onEvent)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onEvent)
  }, [])

  if (!open) {
    return null
  }

  const signInAgain = async () => {
    try {
      await getUserManager()?.removeUser()
    } finally {
      window.location.assign('/')
    }
  }

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="session-expired-title"
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-900 p-4"
    >
      <div className="w-full max-w-sm rounded-xl bg-white p-6 text-center shadow-xl">
        <h2 id="session-expired-title" className="text-lg font-semibold">
          Phiên đăng nhập đã hết hạn
        </h2>
        <p className="mt-2 text-sm text-slate-600">{SESSION_EXPIRED_MESSAGE}</p>
        <button
          type="button"
          autoFocus
          onClick={() => void signInAgain()}
          className="mt-5 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Đăng nhập lại
        </button>
      </div>
    </div>
  )
}
