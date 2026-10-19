import { describe, expect, it, vi } from 'vitest'
import type { User } from 'oidc-client-ts'
import { RENEW_MARGIN_SECONDS, renewSession } from '../src/auth/oidc'

function fakeManager(initial: { expires_in: number } | null) {
  let current: Partial<User> | null = initial
    ? { access_token: 'old', expires_in: initial.expires_in }
    : null
  const signinSilent = vi.fn(
    async (args?: { silentRequestTimeoutInSeconds?: number }) => {
      void args
      await new Promise((resolve) => setTimeout(resolve, 20))
      current = { access_token: 'new', expires_in: 900 }
      return current as User
    },
  )
  return {
    manager: {
      getUser: vi.fn(async () => current as User | null),
      signinSilent,
    },
    signinSilent,
  }
}

describe('renewSession (PR #133 review)', () => {
  it('opens one iframe for many calls at once (4 page images, token just expired)', async () => {
    const { manager, signinSilent } = fakeManager({ expires_in: 0 })
    const users = await Promise.all(
      [1, 2, 3, 4].map(() => renewSession(manager)),
    )
    expect(signinSilent).toHaveBeenCalledTimes(1)
    expect(users.map((u) => u?.access_token)).toEqual([
      'new',
      'new',
      'new',
      'new',
    ])
  })

  it('uses the token another tab just renewed, without an iframe', async () => {
    const { manager, signinSilent } = fakeManager({
      expires_in: RENEW_MARGIN_SECONDS + 300,
    })
    await expect(renewSession(manager)).resolves.toMatchObject({
      access_token: 'old',
    })
    expect(signinSilent).not.toHaveBeenCalled()
  })

  it('renews when the token is about to expire', async () => {
    const { manager, signinSilent } = fakeManager({
      expires_in: RENEW_MARGIN_SECONDS,
    })
    await renewSession(manager)
    expect(signinSilent).toHaveBeenCalledTimes(1)
  })

  it('always asks Keycloak when forced (another tab logged in)', async () => {
    const { manager, signinSilent } = fakeManager({ expires_in: 900 })
    await expect(renewSession(manager, { force: true })).resolves.toMatchObject(
      {
        access_token: 'new',
      },
    )
    expect(signinSilent).toHaveBeenCalledTimes(1)
  })

  it('passes a shorter iframe timeout for the first session on page load', async () => {
    const { manager, signinSilent } = fakeManager(null)
    await renewSession(manager, { timeoutSeconds: 10 })
    expect(signinSilent).toHaveBeenCalledWith({
      forceIframeAuth: true,
      silentRequestTimeoutInSeconds: 10,
    })
  })

  it('runs a new renewal after the previous one finished', async () => {
    const { manager, signinSilent } = fakeManager({ expires_in: 0 })
    await renewSession(manager)
    await renewSession(manager, { force: true })
    expect(signinSilent).toHaveBeenCalledTimes(2)
  })
})
