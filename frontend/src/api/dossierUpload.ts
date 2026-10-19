import { useSyncExternalStore } from 'react'
import { asUploadPdf } from '../pdf/imageToPdf'
import { STRUCTURE_MODE_KEY, type StructureMode } from '../structure'
import {
  createDossier,
  createDossierErrorMessage,
  patchDossier,
} from './dossiers'

/**
 * Tải hồ sơ lên ở ngoài trang Tải lên: bấm tải lên là sang trang tiến trình
 * ngay, việc gửi tệp vẫn chạy tiếp và trang tiến trình đọc % ở đây.
 * Chỉ sống trong tab này: tải lại trang là mất (có cảnh báo trước khi rời).
 */

export type DossierUploadInput = {
  name: string
  code: string
  structureMode: StructureMode
  contract: File
  annexes: File[]
}

export type DossierUploadStatus =
  // Ảnh đang được gói thành PDF.
  | 'preparing'
  // Đang gửi byte lên.
  | 'sending'
  // Đã gửi hết, máy chủ đang kiểm tra và lưu tệp.
  | 'saving'
  | 'done'
  | 'failed'
  | 'cancelled'

export type DossierUpload = {
  id: string
  name: string
  structureMode: StructureMode
  fileCount: number
  /** Giữ tệp đã chọn để quay lại trang Tải lên khi lỗi; bỏ khi đã xong. */
  input: DossierUploadInput | null
  status: DossierUploadStatus
  loaded: number
  total: number
  startedAt: number
  finishedAt: number | null
  dossierId: string | null
  error: string | null
}

const uploads = new Map<string, DossierUpload>()
const controllers = new Map<string, AbortController>()
const listeners = new Set<() => void>()

export function isUploadActive(upload: DossierUpload | null | undefined) {
  return (
    upload?.status === 'preparing' ||
    upload?.status === 'sending' ||
    upload?.status === 'saving'
  )
}

function warnBeforeLeave(event: BeforeUnloadEvent) {
  event.preventDefault()
}

function update(id: string, patch: Partial<DossierUpload>) {
  const current = uploads.get(id)
  if (!current) return
  uploads.set(id, { ...current, ...patch })
  // Đóng tab hay tải lại trang giữa chừng là mất lần tải lên này.
  if (typeof window !== 'undefined') {
    if ([...uploads.values()].some(isUploadActive)) {
      window.addEventListener('beforeunload', warnBeforeLeave)
    } else window.removeEventListener('beforeunload', warnBeforeLeave)
  }
  for (const listener of listeners) listener()
}

async function run(id: string, input: DossierUploadInput) {
  const controller = controllers.get(id)
  const signal = controller?.signal
  try {
    // Ảnh được gói thành PDF một trang để backend và OCR dùng chung luồng PDF.
    const contract = await asUploadPdf(input.contract)
    const annexes = await Promise.all(input.annexes.map(asUploadPdf))
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    const total = [contract, ...annexes].reduce(
      (sum, file) => sum + file.size,
      0,
    )
    update(id, { status: 'sending', loaded: 0, total })

    const created = await createDossier(
      {
        contract,
        metadata: { name: input.name },
        annexes,
      },
      {
        signal,
        // Quá UPLOAD_STALL_TIMEOUT_MS không gửi thêm được byte nào thì client
        // tự huỷ và ném UploadStalledError: lần tải lên thành 'failed'.
        onProgress: (sent, bodyTotal) =>
          update(id, {
            loaded: sent,
            total: bodyTotal,
            status: sent >= bodyTotal ? 'saving' : 'sending',
          }),
      },
    )
    controllers.delete(id)
    if (!created?.dossier_id) {
      update(id, {
        status: 'failed',
        error: 'Không tạo được hồ sơ. Vui lòng thử lại.',
        finishedAt: Date.now(),
      })
      return
    }
    update(id, { status: 'saving', dossierId: created.dossier_id })

    const extra: Record<string, unknown> = {
      privacy: 'private',
      [STRUCTURE_MODE_KEY]: input.structureMode,
    }
    if (input.code) extra.code = input.code
    try {
      await patchDossier(created.dossier_id, { metadata: extra })
    } catch {
      // POST đã tạo hồ sơ. PATCH chỉ ghi field UI thừa so với OpenAPI.
      // Loại cấu trúc vẫn được truyền qua state để trang cây dùng ngay.
    }
    update(id, { status: 'done', input: null, finishedAt: Date.now() })
  } catch (cause) {
    controllers.delete(id)
    if (signal?.aborted) {
      update(id, { status: 'cancelled', finishedAt: Date.now() })
      return
    }
    update(id, {
      status: 'failed',
      error:
        createDossierErrorMessage(cause) ??
        'Không tải lên được. Vui lòng thử lại.',
      finishedAt: Date.now(),
    })
  }
}

/** Bắt đầu tải lên; trả mã để trang tiến trình theo dõi. */
export function startDossierUpload(input: DossierUploadInput) {
  // Lần lỗi/huỷ trước vẫn giữ tệp gốc (tới vài trăm MB): lần mới thay nó.
  for (const [key, upload] of uploads) {
    if (upload.status === 'failed' || upload.status === 'cancelled') {
      uploads.delete(key)
      controllers.delete(key)
    }
  }
  const id = crypto.randomUUID()
  uploads.set(id, {
    id,
    name: input.name,
    structureMode: input.structureMode,
    fileCount: 1 + input.annexes.length,
    input,
    status: 'preparing',
    loaded: 0,
    total: [input.contract, ...input.annexes].reduce(
      (sum, file) => sum + file.size,
      0,
    ),
    startedAt: Date.now(),
    finishedAt: null,
    dossierId: null,
    error: null,
  })
  controllers.set(id, new AbortController())
  update(id, {})
  void run(id, input)
  return id
}

/**
 * Hủy khi còn đang gửi byte. Gửi hết rồi thì máy chủ vẫn tạo hồ sơ, nên không
 * hủy nữa và trả false.
 */
export function cancelDossierUpload(id: string) {
  const upload = uploads.get(id)
  if (upload?.status !== 'preparing' && upload?.status !== 'sending') {
    return false
  }
  controllers.get(id)?.abort()
  return true
}

/**
 * Form đã lấy lại tệp của lần lỗi/huỷ để sửa rồi tải lại: bỏ entry đó, không
 * giữ tệp trong bộ nhớ tới khi tải lại tab. Lần còn chạy hay đã xong thì giữ.
 */
export function releaseDossierUpload(id: string) {
  const upload = uploads.get(id)
  if (upload?.status !== 'failed' && upload?.status !== 'cancelled') return
  uploads.delete(id)
  controllers.delete(id)
  for (const listener of listeners) listener()
}

export function getDossierUpload(id: string | null | undefined) {
  return id ? (uploads.get(id) ?? null) : null
}

function findUpload(id: string | null, dossierId: string | null) {
  if (id) return uploads.get(id) ?? null
  if (!dossierId) return null
  for (const upload of uploads.values()) {
    if (upload.dossierId === dossierId) return upload
  }
  return null
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Lần tải lên theo mã, hoặc lần đã tạo ra hồ sơ `dossierId` trong tab này. */
export function useDossierUpload(
  id: string | null,
  dossierId: string | null = null,
) {
  return useSyncExternalStore(subscribe, () => findUpload(id, dossierId))
}

/** % số byte đã gửi; null khi chưa biết tổng. */
export function uploadPercent(upload: DossierUpload) {
  if (upload.status === 'done' || upload.status === 'saving') return 100
  if (upload.total <= 0) return null
  return Math.min(100, Math.round((upload.loaded / upload.total) * 100))
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
