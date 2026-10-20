import { describe, expect, it } from 'vitest'
import {
  AI2_DASHBOARD_UID,
  grafanaFrameUrl,
  withDashboardUid,
} from '../src/api/monitoring'

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

describe('withDashboardUid', () => {
  it('points the same session path at the AI2 dashboard, query kept', () => {
    expect(
      withDashboardUid('/grafana/d/ci-overview?orgId=1&kiosk', AI2_DASHBOARD_UID),
    ).toBe('/grafana/d/ai2-cost?orgId=1&kiosk')
  })

  it('leaves a path that is not a dashboard untouched, so framing still refuses it', () => {
    const path = withDashboardUid('/api/v1/users', AI2_DASHBOARD_UID)
    expect(path).toBe('/api/v1/users')
    expect(() => grafanaFrameUrl(path, 'https://api.example.com')).toThrow()
  })
})
