import { getAccessToken, tenantIdFromToken } from '../auth/oidc'

export const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8080'
).replace(/\/$/, '')

type ApiEnvelope<T> = {
  data: T
  meta?: {
    trace_id?: string | null
    request_id?: string | null
    page?: number | null
    page_size?: number | null
    total?: number | null
  }
}

type ProblemBody = {
  title?: string
  detail?: string
  code?: string
}

export class ApiError extends Error {
  status: number
  code?: string

  constructor(status: number, message: string, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

function messageFromBody(
  status: number,
  body: unknown,
): {
  message: string
  code?: string
} {
  if (body && typeof body === 'object') {
    const problem = body as ProblemBody
    const message = problem.detail || problem.title
    if (message) {
      return { message, code: problem.code }
    }
  }
  return { message: `API ${status}` }
}

export async function apiFetch(
  path: string,
  init: RequestInit & { accessToken?: string } = {},
): Promise<Response> {
  const { accessToken: overrideToken, ...rest } = init
  const token = overrideToken ?? (await getAccessToken())
  const headers = new Headers(rest.headers)

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
    const tenantId = tenantIdFromToken(token)
    if (tenantId) {
      headers.set('X-Tenant-Id', tenantId)
    }
  }

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }
  headers.set('X-Request-Id', crypto.randomUUID())

  return fetch(`${apiBaseUrl}${path}`, {
    ...rest,
    headers,
  })
}

export async function getJson<T>(
  path: string,
  init: RequestInit & { accessToken?: string } = {},
): Promise<T> {
  const response = await apiFetch(path, init)
  const body: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const { message, code } = messageFromBody(response.status, body)
    throw new ApiError(response.status, message, code)
  }

  if (body && typeof body === 'object' && 'data' in body) {
    return (body as ApiEnvelope<T>).data
  }

  return body as T
}
