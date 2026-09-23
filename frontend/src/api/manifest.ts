import { ApiError, getJson, requestJson } from './client'

export const documentRoles = ['contract', 'annex'] as const
export const relationTypes = [
  'annex_of',
  'amends',
  'supersedes',
  'supplements',
] as const

export type DocumentRole = (typeof documentRoles)[number]
export type RelationType = (typeof relationTypes)[number]
export type RelationConfirmation = 'unconfirmed' | 'confirmed' | 'rejected'
export type ManifestStatus = 'pending' | 'confirmed'

export type ManifestMember = {
  document_id: string
  filename: string
  role: string
  included: boolean
  order_index: number
  page_count?: number | null
  file_size_bytes?: number | null
}

export type ManifestRelation = {
  id: string
  source_document_id: string
  target_document_id: string
  relation_type: string
  confirmation: RelationConfirmation
}

export type Manifest = {
  dossier_id: string
  status: ManifestStatus
  version: number
  latest_job_status?: string | null
  members: ManifestMember[]
  relations: ManifestRelation[]
  confirmed_at?: string | null
}

export type ManifestConfirmMember = {
  document_id: string
  role: DocumentRole
  included: boolean
}

export type ManifestConfirmRelation = {
  id: string | null
  source_document_id: string
  target_document_id: string
  relation_type: RelationType
  confirmation: 'confirmed' | 'rejected'
}

export type ManifestConfirmInput = {
  version: number
  members: ManifestConfirmMember[]
  relations: ManifestConfirmRelation[]
}

export function isDocumentRole(value: string): value is DocumentRole {
  return (documentRoles as readonly string[]).includes(value)
}

export function isRelationType(value: string): value is RelationType {
  return (relationTypes as readonly string[]).includes(value)
}

export function manifestConfirmPath(dossierId: string) {
  return `/xac-nhan-manifest/${encodeURIComponent(dossierId)}`
}

function manifestApiPath(dossierId: string) {
  return `/api/v1/dossiers/${encodeURIComponent(dossierId)}/manifest`
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function asString(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function asOptionalNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asConfirmation(value: unknown): RelationConfirmation {
  if (value === 'confirmed' || value === 'rejected') return value
  return 'unconfirmed'
}

export function normalizeManifest(value: unknown): Manifest | null {
  const record = asRecord(value)
  if (!record) return null
  const dossierId = asString(record.dossier_id)
  if (!dossierId) return null

  const members: ManifestMember[] = []
  const memberRows = Array.isArray(record.members) ? record.members : []
  for (const item of memberRows) {
    const row = asRecord(item)
    if (!row) continue
    const documentId = asString(row.document_id)
    if (!documentId) continue
    members.push({
      document_id: documentId,
      filename: asString(row.filename),
      role: asString(row.role),
      included: row.included !== false,
      order_index: asNumber(row.order_index),
      page_count: asOptionalNumber(row.page_count),
      file_size_bytes: asOptionalNumber(row.file_size_bytes),
    })
  }

  const relations: ManifestRelation[] = []
  const relationRows = Array.isArray(record.relations) ? record.relations : []
  for (const item of relationRows) {
    const row = asRecord(item)
    if (!row) continue
    const sourceId = asString(row.source_document_id)
    const targetId = asString(row.target_document_id)
    if (!sourceId || !targetId) continue
    relations.push({
      id: asString(row.id),
      source_document_id: sourceId,
      target_document_id: targetId,
      relation_type: asString(row.relation_type),
      confirmation: asConfirmation(row.confirmation),
    })
  }

  return {
    dossier_id: dossierId,
    status: record.status === 'confirmed' ? 'confirmed' : 'pending',
    version: asNumber(record.version),
    latest_job_status:
      typeof record.latest_job_status === 'string'
        ? record.latest_job_status
        : null,
    members,
    relations,
    confirmed_at:
      typeof record.confirmed_at === 'string' ? record.confirmed_at : null,
  }
}

export async function getManifest(dossierId: string, signal?: AbortSignal) {
  const data = await getJson<unknown>(manifestApiPath(dossierId), { signal })
  const manifest = normalizeManifest(data)
  if (!manifest) {
    throw new Error('Backend không trả manifest hợp lệ.')
  }
  return manifest
}

export async function confirmManifest(
  dossierId: string,
  input: ManifestConfirmInput,
) {
  const { data } = await requestJson<unknown>(
    `${manifestApiPath(dossierId)}/confirm`,
    { method: 'POST', json: input },
  )
  const manifest = normalizeManifest(data)
  if (!manifest) {
    throw new Error('Backend không trả manifest hợp lệ.')
  }
  return manifest
}

export function manifestErrorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return null
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Phiên đăng nhập hết hạn. Đăng nhập lại.'
    }
    if (error.status === 403) {
      return 'Chỉ vận hành và quản trị mới xác nhận manifest được.'
    }
    if (
      error.status === 404 &&
      error.message.trim().toLowerCase() === 'not found'
    ) {
      return 'API xác nhận manifest chưa có trên backend.'
    }
    if (error.status === 404) {
      return 'Không tìm thấy hồ sơ này.'
    }
    if (error.code === 'manifest_already_confirmed') {
      return 'Manifest này đã được xác nhận.'
    }
    if (error.code === 'manifest_version_conflict') {
      return 'Manifest vừa được sửa ở nơi khác.'
    }
    if (error.status === 409) {
      return error.message || 'Manifest đang xung đột. Tải lại rồi thử lại.'
    }
    if (error.code === 'relations_unconfirmed') {
      return 'Còn quan hệ chưa xác nhận.'
    }
    if (error.code === 'contract_required') {
      return 'Hồ sơ cần ít nhất một hợp đồng chính thuộc hồ sơ.'
    }
    if (error.code === 'member_role_invalid') {
      return 'Vai trò tài liệu không hợp lệ.'
    }
    if (error.code === 'member_missing') {
      return 'Thiếu tài liệu của hồ sơ trong xác nhận.'
    }
    if (error.code === 'member_unknown') {
      return 'Có tài liệu không thuộc hồ sơ này.'
    }
    if (error.code === 'relation_missing') {
      return 'Thiếu quan hệ đang có trên hồ sơ.'
    }
    if (error.code === 'relation_member_invalid') {
      return 'Quan hệ phải nối hai tài liệu đang thuộc hồ sơ.'
    }
    if (error.code === 'relation_duplicate') {
      return 'Quan hệ bị trùng.'
    }
    if (error.code === 'relation_self') {
      return 'Quan hệ phải nối hai tài liệu khác nhau.'
    }
    if (error.code === 'relation_type_invalid') {
      return 'Loại quan hệ không hợp lệ.'
    }
    if (error.status === 422) {
      return error.message || 'Dữ liệu xác nhận không hợp lệ.'
    }
    return error.message
  }
  if (error instanceof TypeError) {
    return 'Không kết nối được backend. API xác nhận manifest chưa sẵn sàng.'
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return 'Không xác nhận được manifest. Thử lại.'
}
