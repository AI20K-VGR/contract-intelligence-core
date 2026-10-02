import { describe, expect, it } from 'vitest'
import { grafanaFrameUrl } from '../src/api/monitoring'

describe('grafanaFrameUrl', () => {
  it('frames the dashboard path on the API origin', () => {
    expect(
      grafanaFrameUrl(
        '/grafana/d/ci-overview?orgId=1&kiosk',
        'https://api.example.com',
      ),
    ).toBe('https://api.example.com/grafana/d/ci-overview?orgId=1&kiosk')
  })

  it.each([
    'https://evil.example/grafana/d/x',
    '//evil.example/grafana/d/x',
    '/api/v1/users',
    '/grafana//evil.example',
  ])('refuses anything but a /grafana/ path: %s', (path) => {
    expect(() => grafanaFrameUrl(path, 'https://api.example.com')).toThrow()
  })
})
