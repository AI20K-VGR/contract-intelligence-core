import { describe, expect, it, vi } from 'vitest'
import { openAuthChannel, AUTH_CHANNEL_NAME } from '../src/auth/authChannel'
import { ErrorResponse, ErrorTimeout } from 'oidc-client-ts'
import { RENEW_LOCK_NAME, withRenewLock } from '../src/auth/renewLock'
import { isSessionEnded } from '../src/auth/sessionEnded'
import {
  MemoryTokenStorage,
  purgeStoredOidcUsers,
  withoutRefreshToken,
} from '../src/auth/tokenStore'

function memoryStorage(entries: Record<string, string>): Storage {
  const map = new Map(Object.entries(entries))
  return {
    get length() {
      return map.size
    },
    key: (index: number) => [...map.keys()][index] ?? null,
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => void map.set(key, value),
    removeItem: (key: string) => void map.delete(key),
    clear: () => map.clear(),
  }
}

const SESSION = JSON.stringify({
  access_token: 'eyJ.access',
  id_token: 'eyJ.id',
  refresh_token: 'eyJ.refresh',
  expires_at: 1,
})

describe('purgeStoredOidcUsers (#130)', () => {
  it('removes every oidc.user:* key left by the old version, and only those', () => {
    const local = memoryStorage({
      'oidc.user:https://auth/realms/ci:frontend': SESSION,
      'oidc.user:https://auth/realms/other:frontend': SESSION,
      'reading-prefs': '{"theme":"dark"}',
    })
    const session = memoryStorage({
      'oidc.user:https://auth/realms/ci:frontend': SESSION,
      'oidc.abc123': '{"code_verifier":"x"}',
    })
    purgeStoredOidcUsers([local, session, null])
    expect(local.length).toBe(1)
    expect(local.getItem('reading-prefs')).toBe('{"theme":"dark"}')
    // state/PKCE của lượt redirect (oidc.<state>) không phải phiên: giữ lại.
    expect(session.length).toBe(1)
    expect(session.getItem('oidc.abc123')).not.toBeNull()
  })

  it('does not throw when the browser blocks storage', () => {
    const blocked = {
      get length(): number {
        throw new Error('SecurityError')
      },
    } as unknown as Storage
    expect(() => purgeStoredOidcUsers([blocked])).not.toThrow()
  })
})

describe('MemoryTokenStorage (#130)', () => {
  it('keeps the session in memory without the refresh token', async () => {
    const store = new MemoryTokenStorage()
    store.setItem('oidc.user:x', SESSION)
    const saved = JSON.parse(store.getItem('oidc.user:x') ?? '{}')
    expect(saved.access_token).toBe('eyJ.access')
    expect(saved.id_token).toBe('eyJ.id')
    expect(saved).not.toHaveProperty('refresh_token')
  })

  it('leaves values that are not a session alone', () => {
    expect(withoutRefreshToken('not json')).toBe('not json')
    expect(withoutRefreshToken('{"a":1}')).toBe('{"a":1}')
  })
})

describe('openAuthChannel (#130)', () => {
  function fakeHub() {
    const members: { onmessage: ((event: MessageEvent) => void) | null }[] = []
    const names: string[] = []
    const create = (name: string) => {
      names.push(name)
      const me = {
        onmessage: null as ((event: MessageEvent) => void) | null,
        postMessage: (data: unknown) => {
          // BroadcastChannel không gửi lại cho chính nó.
          for (const other of members)
            if (other !== me) other.onmessage?.({ data } as MessageEvent)
        },
        close: () => {
          members.splice(members.indexOf(me), 1)
        },
      }
      members.push(me)
      return me
    }
    return { create, names }
  }

  it('tells the other tabs about a logout, not the tab that sent it', () => {
    const hub = fakeHub()
    const tabA = vi.fn()
    const tabB = vi.fn()
    const a = openAuthChannel(tabA, hub.create)
    openAuthChannel(tabB, hub.create)
    a.post('logout')
    expect(tabB).toHaveBeenCalledWith('logout')
    expect(tabA).not.toHaveBeenCalled()
    expect(hub.names).toEqual([AUTH_CHANNEL_NAME, AUTH_CHANNEL_NAME])
  })

  it('ignores unknown messages and stops after close', () => {
    const hub = fakeHub()
    const tabB = vi.fn()
    const a = openAuthChannel(() => {}, hub.create)
    const b = openAuthChannel(tabB, hub.create)
    a.post('hello' as never)
    expect(tabB).not.toHaveBeenCalled()
    b.close()
    a.post('login')
    expect(tabB).not.toHaveBeenCalled()
  })

  it('does nothing when BroadcastChannel is missing', () => {
    const channel = openAuthChannel(
      () => {},
      () => null,
    )
    expect(() => channel.post('logout')).not.toThrow()
  })
})

describe('withRenewLock (#130)', () => {
  it('runs the renewal under the lexis-refresh lock', async () => {
    const request = vi.fn(<T>(_name: string, callback: () => Promise<T>) =>
      callback(),
    )
    await expect(withRenewLock(async () => 'ok', { request })).resolves.toBe(
      'ok',
    )
    expect(request).toHaveBeenCalledWith(RENEW_LOCK_NAME, expect.any(Function))
  })

  it('runs it directly without Web Locks', async () => {
    await expect(withRenewLock(async () => 7, null)).resolves.toBe(7)
  })
})

describe('isSessionEnded (#130)', () => {
  it('ends the session only when Keycloak says so', () => {
    expect(isSessionEnded(new ErrorResponse({ error: 'login_required' }))).toBe(
      true,
    )
    expect(
      isSessionEnded(new ErrorResponse({ error: 'interaction_required' })),
    ).toBe(true)
  })

  it('keeps the user on a slow or failed renewal', () => {
    // Tab chạy nền bị làm chậm: iframe quá thời gian chờ, phiên vẫn còn.
    expect(
      isSessionEnded(new ErrorTimeout('IFrame timed out without a response')),
    ).toBe(false)
    expect(isSessionEnded(new TypeError('Failed to fetch'))).toBe(false)
    expect(
      isSessionEnded(new ErrorResponse({ error: 'temporarily_unavailable' })),
    ).toBe(false)
  })
})
