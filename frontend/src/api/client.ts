import { getAccessToken, tenantIdFromToken } from '../auth/oidc'
import {
  notifySessionExpired,
  SESSION_EXPIRED_MESSAGE,
} from '../auth/sessionExpired'

export const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
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

function withApiHeaders(headers: Headers, token: string | null) {
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
  return headers
}

export async function apiFetch(
  path: string,
  init: RequestInit & { accessToken?: string } = {},
): Promise<Response> {
  const { accessToken: overrideToken, ...rest } = init
  const token = overrideToken ?? (await getAccessToken())
  const headers = withApiHeaders(new Headers(rest.headers), token)

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...rest,
    headers,
  })
  if (response.status === 401 && token) {
    notifySessionExpired()
  }
  return response
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
  return parseApiResponse<T>(response.status, response.ok, payload)
}

function parseApiResponse<T>(
  status: number,
  ok: boolean,
  payload: unknown,
): { data: T; meta?: ApiMeta } {
  if (!ok) {
    const { message: rawMessage, code } = messageFromBody(status, payload)
    const message = status === 401 ? SESSION_EXPIRED_MESSAGE : rawMessage
    throw new ApiError(status, message, code, payload)
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

export const UPLOAD_STALLED_MESSAGE = 'Mạng chậm hoặc bị ngắt, vui lòng thử lại.'

/** Không gửi thêm được byte nào trong `stallTimeoutMs`: tải lên đã bị huỷ. */
export class UploadStalledError extends Error {
  constructor() {
    super(UPLOAD_STALLED_MESSAGE)
    this.name = 'UploadStalledError'
  }
}

/** Sau ngần này không gửi thêm được byte nào thì huỷ tải lên. */
export const UPLOAD_STALL_TIMEOUT_MS = 30_000

export type UploadOptions = {
  /** Số byte đã gửi / tổng số byte của body multipart. */
  onProgress?: (sent: number, total: number) => void
  stallTimeoutMs?: number
  signal?: AbortSignal
}

/**
 * POST multipart bằng XMLHttpRequest: `fetch` không báo tiến độ gửi body.
 * Đồng hồ treo chỉ chạy khi còn byte phải gửi; gửi xong thì chờ máy chủ trả lời
 * như `requestJson`. Lỗi trả về giống `requestJson` (ApiError, 401 hết phiên),
 * mất kết nối là TypeError như `fetch`.
 */
export async function postMultipartWithProgress<T>(
  path: string,
  formData: FormData,
  options: UploadOptions = {},
): Promise<{ data: T; meta?: ApiMeta }> {
  const { onProgress, stallTimeoutMs = UPLOAD_STALL_TIMEOUT_MS, signal } = options
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  const token = await getAccessToken()
  const headers = withApiHeaders(new Headers(), token)

  const { status, payload } = await new Promise<{
    status: number
    payload: unknown
  }>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    let stallTimer: ReturnType<typeof setTimeout> | undefined
    let settled = false

    const stopStallTimer = () => {
      if (stallTimer !== undefined) clearTimeout(stallTimer)
      stallTimer = undefined
    }
    const finish = (fn: () => void) => {
      if (settled) return
      settled = true
      stopStallTimer()
      signal?.removeEventListener('abort', onAbort)
      fn()
    }
    const armStallTimer = () => {
      stopStallTimer()
      stallTimer = setTimeout(() => {
        finish(() => reject(new UploadStalledError()))
        xhr.abort()
      }, stallTimeoutMs)
    }
    const onAbort = () => {
      finish(() => reject(new DOMException('Aborted', 'AbortError')))
      xhr.abort()
    }

    xhr.open('POST', `${apiBaseUrl}${path}`)
    // Browser must set multipart boundary. Do not set Content-Type.
    headers.forEach((value, key) => xhr.setRequestHeader(key, value))
    xhr.upload.onprogress = (event) => {
      armStallTimer()
      if (event.lengthComputable) onProgress?.(event.loaded, event.total)
    }
    // Gửi xong body: từ đây chỉ còn chờ máy chủ xử lý.
    xhr.upload.onload = stopStallTimer
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null
      } catch {
        body = null
      }
      finish(() => resolve({ status: xhr.status, payload: body }))
    }
    xhr.onerror = () => finish(() => reject(new TypeError('Failed to fetch')))
    xhr.onabort = () =>
      finish(() => reject(new DOMException('Aborted', 'AbortError')))
    signal?.addEventListener('abort', onAbort)

    armStallTimer()
    xhr.send(formData)
  })

  if (status === 401 && token) {
    notifySessionExpired()
  }
  return parseApiResponse<T>(status, status >= 200 && status < 300, payload)
}
