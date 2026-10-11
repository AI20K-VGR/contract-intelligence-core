import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import { AppLayout } from './AppLayout'

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ user: null, logout: vi.fn() }),
}))

describe('AppLayout mobile navigation', () => {
  it('keeps dossier content full-width and exposes a closed nav drawer on mobile', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/cau-truc/demo-dossier']}>
        <AppLayout role="user" />
      </MemoryRouter>,
    )

    expect(html).toContain('left-0 right-0')
    expect(html).toContain('md:left-64')
    expect(html).toContain('pl-0 md:pl-64')
    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('aria-controls="primary-navigation"')
    expect(html).toContain('id="primary-navigation"')
    expect((html.match(/<button aria-label=/g) ?? []).length).toBeGreaterThan(1)
    expect(html).toContain('invisible -translate-x-full')
  })
})
