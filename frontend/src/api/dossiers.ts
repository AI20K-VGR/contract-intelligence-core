import { ApiError, postMultipart, requestJson } from './client'

/** OpenAPI `1.1.0+sprint4-ai-integration` — POST /api/v1/dossiers */
export type CreateDossierMetadata = {
  name: string
  tags?: string[]
  notes?: string
}

export type DossierCreated = {
  dossier_id: string
  job_id?: string | null
}

export type CreateDossierInput = {
  contract: File
  metadata: CreateDossierMetadata
  annexes?: File[]
}

/** OpenAPI DossierUpdateBody — PATCH /api/v1/dossiers/{dossier_id} */
export type DossierUpdateBody = {
  name?: string | null
  metadata?: Record<string, unknown> | null
}

const DOSSIERS_PATH = '/api/v1/dossiers'

export async function createDossier(input: CreateDossierInput) {
  const form = new FormData()
  form.append('contract', input.contract)
  form.append('metadata', JSON.stringify(input.metadata))
  for (const annex of input.annexes ?? []) {
    form.append('annexes', annex)
  }

  const { data } = await postMultipart<DossierCreated>(DOSSIERS_PATH, form)
  return data
}

export async function patchDossier(dossierId: string, body: DossierUpdateBody) {
  const { data } = await requestJson<unknown>(
    `${DOSSIERS_PATH}/${encodeURIComponent(dossierId)}`,
    { method: 'PATCH', json: body },
  )
  return data
}

export function createDossierErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return null
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    }
    if (error.status === 403) {
      return 'Chỉ vận hành và quản trị mới tải hồ sơ được.'
    }
    if (error.status === 404 && error.message === 'Not Found') {
      return 'API tạo hồ sơ chưa có trên backend.'
    }
    if (error.status === 404) {
      return 'Không tìm thấy hồ sơ này.'
    }
    if (error.status === 409) {
      return 'Hồ sơ đang xung đột. Thử lại sau.'
    }
    if (error.status === 422) {
      return (
        error.message || 'Metadata không đúng JSON { name, tags?, notes? }.'
      )
    }
    if (error.status === 400) {
      return error.message || 'Thiếu tệp PDF hợp đồng.'
    }
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được backend. API tạo hồ sơ chưa sẵn sàng.'
  }
  return 'Không tải được hồ sơ. Thử lại.'
}
