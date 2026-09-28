import { useEffect } from 'react'
import { getUserManager } from '../auth/oidc'

export function SilentRenewPage() {
  useEffect(() => {
    void getUserManager()?.signinSilentCallback()
  }, [])

  return null
}
