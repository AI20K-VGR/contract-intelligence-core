import {
  ApiError,
  requestJson,
  sendWithProgress,
  UploadStalledError,
  type UploadOptions,
} from './client'
import {
  createDossier,
  type CreateDossierInput,
  type DossierCreated,
} from './dossiers'

/**
 * Tải hồ sơ theo khúc (`/uploads`, DOC-05b v4.2.0, #145).
 *
 * Cloudflare gói Free cắt request còn đang gửi body sau khoảng 125 giây, nên trên
 * mạng chậm một `POST /dossiers` chỉ gửi kịp vài MB. Ở đây mỗi khúc (mặc định
 * 1 MiB, server quyết) là một request ngắn: khúc lỗi thì gửi lại riêng khúc đó,
 * rồi `complete` ghép các khúc và tạo hồ sơ như `POST /dossiers`.
 */

const UPLOADS_PATH = '/api/v1/uploads'

/** Số lần gửi một khúc (lần đầu + gửi lại) trước khi báo lỗi. */
export const CHUNK_ATTEMPTS = 4
/** Chờ trước mỗi lần gửi lại: 2 s, 4 s, 8 s. */
const RETRY_DELAYS_MS = [2000, 4000, 8000]
/**
 * Chờ `complete` xong khi request bị cắt (Cloudflare 524 sau khoảng 100 s) hay
 * server báo phiên đang `completing`: hỏi lại mỗi 3 s, tối đa 3 phút.
 */
const COMPLETE_POLL_MS = 3000
const COMPLETE_WAIT_MS = 180_000

export type UploadSessionFile = {
  index: number
  role: string
  filename: string
  size: number
  chunks: number
  received: number[]
}

export type UploadSession = {
  upload_id: string
  status: 'open' | 'completing' | 'completed' | 'cancelled'
  chunk_size: number
  expires_at: string
  files: UploadSessionFile[]
  dossier_id?: string | null
  job_id?: string | null
}

export type ChunkedUploadDeps = {
  openSession: (body: unknown, signal?: AbortSignal) => Promise<UploadSession>
  getSession: (id: string, signal?: AbortSignal) => Promise<UploadSession>
  sendChunk: (path: string, blob: Blob, options: UploadOptions) => Promise<void>
  complete: (id: string, signal?: AbortSignal) => Promise<DossierCreated>
  cancel: (id: string) => Promise<void>
  /** Backend trước v4.2.0 (chưa có `/uploads`): một `POST /dossiers` như cũ. */
  legacyCreate: (
    input: CreateDossierInput,
    options: UploadOptions,
  ) => Promise<DossierCreated>
  sleep: (ms: number, signal?: AbortSignal) => Promise<void>
}

function abortError() {
  return new DOMException('Aborted', 'AbortError')
}

function isAbort(cause: unknown) {
  return cause instanceof DOMException && cause.name === 'AbortError'
}

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError())
      return
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    const onAbort = () => {
      clearTimeout(timer)
      reject(abortError())
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

const defaultDeps: ChunkedUploadDeps = {
  openSession: async (body, signal) =>
    (
      await requestJson<UploadSession>(UPLOADS_PATH, {
        method: 'POST',
        json: body,
        signal,
      })
    ).data,
  getSession: async (id, signal) =>
    (
      await requestJson<UploadSession>(
        `${UPLOADS_PATH}/${encodeURIComponent(id)}`,
        { signal },
      )
    ).data,
  sendChunk: async (path, blob, options) => {
    await sendWithProgress('PUT', path, blob, {
      ...options,
      contentType: 'application/octet-stream',
    })
  },
  complete: async (id, signal) =>
    (
      await requestJson<DossierCreated>(
        `${UPLOADS_PATH}/${encodeURIComponent(id)}/complete`,
        { method: 'POST', json: {}, signal },
      )
    ).data,
  cancel: async (id) => {
    await requestJson(`${UPLOADS_PATH}/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
  },
  legacyCreate: (input, options) => createDossier(input, options),
  sleep,
}

/** Lỗi đáng gửi lại khúc: mất mạng, treo, máy chủ hay Cloudflare lỗi tạm. */
function isTransient(cause: unknown) {
  if (cause instanceof TypeError || cause instanceof UploadStalledError) {
    return true
  }
  return (
    cause instanceof ApiError &&
    (cause.status === 408 || cause.status === 429 || cause.status >= 500)
  )
}

/**
 * Lỗi đáng chờ rồi hỏi lại `/complete`: Cloudflare hoặc gateway trả lỗi tạm
 * nhưng server có thể đã tiếp nhận request. Các lỗi 5xx khác (500, 501, 504…)
 * thường là bug server, không retry vì có thể tạo hồ sơ trùng.
 */
const COMPLETE_RETRY_CODES = new Set([502, 503, 524])

function isCompleteRetryable(cause: unknown) {
  // Mất mạng lúc chờ phản hồi: server có thể đã tạo hồ sơ. Hỏi lại phiên là
  // an toàn vì gọi lại /complete trả đúng hồ sơ đó; bỏ qua thì người dùng
  // thấy lỗi, tải lại và có hồ sơ trùng.
  if (cause instanceof TypeError) return true
  return (
    cause instanceof ApiError &&
    (cause.code === 'UPLOAD_COMPLETING' ||
      COMPLETE_RETRY_CODES.has(cause.status))
  )
}

/** `details` của lỗi /uploads: khung `{"error": {code, message, details}}` (DOC-05b §3.3). */
function errorDetails(cause: ApiError): Record<string, unknown> {
  const body = cause.details as
    { error?: { details?: unknown }; detail?: unknown } | null | undefined
  const details = body?.error?.details ?? body?.detail
  return details && typeof details === 'object'
    ? (details as Record<string, unknown>)
    : {}
}

/** `{ "<index>": [n, …] }` của `409 UPLOAD_MISSING_CHUNKS`; null khi lỗi khác. */
function missingChunks(cause: unknown): Record<string, number[]> | null {
  if (!(cause instanceof ApiError) || cause.status !== 409) return null
  const raw = errorDetails(cause).missing_chunks
  if (!raw || typeof raw !== 'object') return null
  const out: Record<string, number[]> = {}
  for (const [index, list] of Object.entries(raw as Record<string, unknown>)) {
    if (Array.isArray(list)) {
      out[index] = list.filter((n): n is number => Number.isInteger(n))
    }
  }
  return out
}

/** Phiên đã thành hồ sơ: lấy đúng phản hồi như `POST /dossiers`. */
function createdFrom(session: UploadSession): DossierCreated | null {
  if (session.status !== 'completed' || !session.dossier_id) return null
  return { dossier_id: session.dossier_id, job_id: session.job_id ?? null }
}

/**
 * Tải hồ sơ theo khúc và trả `{dossier_id, job_id}` như `createDossier`.
 * `onProgress(sent, total)` tính trên tổng byte của mọi tệp; gửi hết thì
 * `sent === total` và còn chờ server ghép tệp, tạo hồ sơ.
 * Huỷ (signal) hay lỗi hẳn thì xoá phiên, để không chiếm chỗ trong giới hạn
 * số phiên đang mở của người dùng.
 */
export async function uploadDossierInChunks(
  input: CreateDossierInput,
  options: UploadOptions = {},
  deps: ChunkedUploadDeps = defaultDeps,
): Promise<DossierCreated> {
  const { signal, onProgress, stallTimeoutMs } = options
  const local = [input.contract, ...(input.annexes ?? [])]
  const files = local.map((file, position) => ({
    role: position === 0 ? 'contract' : 'annex',
    filename: file.name,
    size: file.size,
  }))

  let session: UploadSession
  try {
    session = await deps.openSession(
      { metadata: input.metadata, files },
      signal,
    )
  } catch (cause) {
    // Backend chưa có /uploads: tải một lần như trước.
    if (cause instanceof ApiError && cause.status === 404) {
      return deps.legacyCreate(input, options)
    }
    throw cause
  }

  const id = session.upload_id
  const total = local.reduce((sum, file) => sum + file.size, 0)
  let sent = 0
  const report = (extra = 0) =>
    onProgress?.(Math.min(total, sent + extra), total)

  async function sendOne(index: number, n: number) {
    const file = local[index]!
    const start = n * session.chunk_size
    const blob = file.slice(
      start,
      Math.min(file.size, start + session.chunk_size),
    )
    const path = `${UPLOADS_PATH}/${encodeURIComponent(id)}/files/${index}/chunks/${n}`
    for (let attempt = 1; ; attempt += 1) {
      try {
        await deps.sendChunk(path, blob, {
          signal,
          stallTimeoutMs,
          onProgress: (loaded) => report(loaded),
        })
        sent += blob.size
        report()
        return
      } catch (cause) {
        if (isAbort(cause) || signal?.aborted) throw abortError()
        if (!isTransient(cause) || attempt >= CHUNK_ATTEMPTS) throw cause
        report()
        await deps.sleep(RETRY_DELAYS_MS[attempt - 1] ?? 8000, signal)
      }
    }
  }

  async function sendMissing(missing: Record<string, number[]>) {
    for (const [index, list] of Object.entries(missing)) {
      const file = local[Number(index)]
      if (!file) continue
      for (const n of list) {
        // Khúc này đã tính vào `sent` ở lần gửi trước: trừ ra rồi gửi lại.
        const start = n * session.chunk_size
        sent -= Math.max(
          0,
          Math.min(file.size, start + session.chunk_size) - start,
        )
        await sendOne(Number(index), n)
      }
    }
  }

  async function finish(): Promise<DossierCreated> {
    const deadline = Date.now() + COMPLETE_WAIT_MS
    let resentMissing = false
    for (;;) {
      try {
        return await deps.complete(id, signal)
      } catch (cause) {
        if (isAbort(cause) || signal?.aborted) throw abortError()
        const missing = missingChunks(cause)
        if (missing && !resentMissing) {
          resentMissing = true
          await sendMissing(missing)
          continue
        }
        // Request khác đang ghép phiên này: chờ rồi hỏi lại, đừng tải lại.
        const completing =
          cause instanceof ApiError && cause.code === 'UPLOAD_COMPLETING'
        if (!completing && !isCompleteRetryable(cause)) throw cause
        if (Date.now() > deadline) throw cause
      }
      // Request bị cắt hay phiên đang được ghép: hỏi xem đã thành hồ sơ chưa.
      await deps.sleep(COMPLETE_POLL_MS, signal)
      try {
        const current = await deps.getSession(id, signal)
        const created = createdFrom(current)
        if (created) return created
        if (current.status === 'cancelled') {
          throw new ApiError(
            409,
            'Phiên tải lên đã bị huỷ.',
            'UPLOAD_CANCELLED',
          )
        }
      } catch (cause) {
        if (isAbort(cause) || signal?.aborted) throw abortError()
        if (!isTransient(cause)) throw cause
      }
    }
  }

  /** Phiên đã thành hồ sơ (`409 UPLOAD_COMPLETED`): lấy hồ sơ đó, không tạo thêm. */
  async function alreadyCreated(
    cause: unknown,
  ): Promise<DossierCreated | null> {
    if (!(cause instanceof ApiError) || cause.code !== 'UPLOAD_COMPLETED') {
      return null
    }
    try {
      const current = await deps.getSession(id, signal)
      const created = createdFrom(current)
      if (created) return created
    } catch {
      // Không đọc được phiên: dùng mã hồ sơ trong lỗi.
    }
    const dossierId = errorDetails(cause).dossier_id
    return typeof dossierId === 'string'
      ? { dossier_id: dossierId, job_id: null }
      : null
  }

  try {
    for (const file of [...session.files].sort((a, b) => a.index - b.index)) {
      const received = new Set(file.received)
      for (let n = 0; n < file.chunks; n += 1) {
        if (signal?.aborted) throw abortError()
        if (received.has(n)) {
          const start = n * session.chunk_size
          sent +=
            Math.min(local[file.index]!.size, start + session.chunk_size) -
            start
          continue
        }
        await sendOne(file.index, n)
      }
    }
    report()
    return await finish()
  } catch (cause) {
    const created = await alreadyCreated(cause)
    if (created) return created
    // Huỷ hay lỗi hẳn: bỏ phiên ở server (không chờ, lỗi cũng bỏ qua).
    void deps.cancel(id).catch(() => {})
    throw cause
  }
}
