import { getAccessToken, tenantIdFromToken } from '../auth/oidc'

export const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8080'
).replace(/\/$/, '')

export type ApiMeta = {
  trace_id?: string | null
  request_id?: string | null
  page?: number | null
  page_size?: number | null
  total?: number | null
}

type ApiEnvelope<T> = {
  data: T
  meta?: ApiMeta
}

type ProblemDetailItem = {
  msg?: string
}

type ProblemBody = {
  title?: string
  detail?: string | ProblemDetailItem[]
  code?: string
  error?: {
    code?: string
    message?: string
  }
}

export class ApiError extends Error {
  status: number
  code?: string
  details?: unknown

  constructor(
    status: number,
    message: string,
    code?: string,
    details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
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
    if (typeof problem.detail === 'string' && problem.detail) {
      return { message: problem.detail, code: problem.code }
    }
    if (Array.isArray(problem.detail)) {
      const message = problem.detail
        .map((item) => item?.msg?.trim() ?? '')
        .filter(Boolean)
        .join(' ')
      if (message) {
        return { message, code: problem.code }
      }
    }
    if (problem.error?.message) {
      return { message: problem.error.message, code: problem.error.code }
    }
    if (problem.title) {
      return { message: problem.title, code: problem.code }
    }
  }
  return { message: `API ${status}` }
}

function unwrapEnvelope<T>(body: unknown): { data: T; meta?: ApiMeta } {
  if (body && typeof body === 'object' && 'data' in body) {
    const envelope = body as ApiEnvelope<T>
    return { data: envelope.data, meta: envelope.meta }
  }
  return { data: body as T }
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
  if (apiBaseUrl.includes('ngrok')) {
    headers.set('ngrok-skip-browser-warning', 'true')
  }
  headers.set('X-Request-Id', crypto.randomUUID())

  return fetch(`${apiBaseUrl}${path}`, {
    ...rest,
    headers,
  })
}

export async function requestJson<T>(
  path: string,
  init: RequestInit & { accessToken?: string; json?: unknown } = {},
): Promise<{ data: T; meta?: ApiMeta }> {
  const { json, headers, ...rest } = init
  const nextHeaders = new Headers(headers)
  let body = rest.body
  if (json !== undefined) {
    nextHeaders.set('Content-Type', 'application/json')
    body = JSON.stringify(json)
  } else if (body instanceof FormData) {
    // Browser must set multipart boundary. Do not set Content-Type.
    nextHeaders.delete('Content-Type')
  }

  const response = await apiFetch(path, {
    ...rest,
    headers: nextHeaders,
    body,
  })
  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const { message, code } = messageFromBody(response.status, payload)
    throw new ApiError(response.status, message, code, payload)
  }

  return unwrapEnvelope<T>(payload)
}

export async function getJson<T>(
  path: string,
  init: RequestInit & { accessToken?: string } = {},
): Promise<T> {
  const { data } = await requestJson<T>(path, init)
  return data
}

export async function postMultipart<T>(
  path: string,
  formData: FormData,
  init: RequestInit & { accessToken?: string } = {},
): Promise<{ data: T; meta?: ApiMeta }> {
  return requestJson<T>(path, {
    ...init,
    method: init.method ?? 'POST',
    body: formData,
  })
}
