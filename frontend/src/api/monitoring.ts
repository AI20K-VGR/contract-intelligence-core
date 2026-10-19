import { apiBaseUrl, requestJson } from './client'

type MonitoringSessionResponse = {
  dashboard_path: string
  expires_in: number
}

export type MonitoringSession = {
  /** Absolute iframe URL on the API origin, e.g. https://api…/grafana/d/ci-overview?kiosk */
  dashboardUrl: string
  /** Same session, AI2's own dashboard (cost and speed of questions and conflict jobs). */
  ai2DashboardUrl: string
  /** Seconds until the /grafana cookie expires; renew before then. */
  expiresIn: number
}

const SESSION_PATH = '/api/v1/admin/monitoring/session'

/** Grafana uid of infra/monitoring/grafana/dashboards/ai2-cost.json. */
export const AI2_DASHBOARD_UID = 'ai2-cost'

/** The backend's dashboard path with another dashboard uid, same query (kiosk, orgId). */
export function withDashboardUid(dashboardPath: string, uid: string) {
  return dashboardPath.replace(/^\/grafana\/d\/[^/?#]+/, `/grafana/d/${uid}`)
}

/**
 * Only a path under /grafana/ on our own API is ever framed, whatever the
 * response says.
 */
export function grafanaFrameUrl(dashboardPath: string, base = apiBaseUrl) {
  if (!dashboardPath.startsWith('/grafana/') || dashboardPath.includes('//')) {
    throw new Error('Đường dẫn dashboard không hợp lệ.')
  }
  return `${base}${dashboardPath}`
}

/**
 * Trade the Keycloak token for the HttpOnly /grafana cookie the dashboard
 * iframe needs (an iframe cannot send a Bearer header). The backend refuses
 * anyone who is not ADMINISTRATOR with 403.
 */
export async function openMonitoringSession(
  signal?: AbortSignal,
): Promise<MonitoringSession> {
  const { data } = await requestJson<MonitoringSessionResponse>(SESSION_PATH, {
    method: 'POST',
    credentials: 'include',
    signal,
  })
  return {
    dashboardUrl: grafanaFrameUrl(data.dashboard_path),
    ai2DashboardUrl: grafanaFrameUrl(
      withDashboardUid(data.dashboard_path, AI2_DASHBOARD_UID),
    ),
    expiresIn: Math.max(60, data.expires_in),
  }
}
