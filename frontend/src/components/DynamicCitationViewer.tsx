import { apiBaseUrl } from '../api/client'

export type CitationViewerStatus = 'LOCATABLE' | 'PARTIAL' | 'UNRESOLVED'
export type CitationViewerScope = 'body' | 'annex' | 'unknown'

export type CitationViewerModel = {
  dossierId: string
  documentId: string | null
  sourceFileId: string | null
  citationId: string | null
  scope: CitationViewerScope
  status: CitationViewerStatus
  quote: string
  pageNo: number | null
  lineId: string | null
  bbox: [number, number, number, number] | null
  documentName?: string | null
  documentRole?: string | null
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function asString(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asBbox(value: unknown): [number, number, number, number] | null {
  if (
    !Array.isArray(value) ||
    value.length !== 4 ||
    !value.every((item) => typeof item === 'number' && Number.isFinite(item))
  ) {
    return null
  }
  return [value[0], value[1], value[2], value[3]]
}

export function normalizeCitationViewerModel(
  value: unknown,
  dossierFallback = '',
): CitationViewerModel | null {
  const row = asRecord(value)
  if (!row) return null
  const status = asString(row.status).toUpperCase()
  const scope = asString(row.scope).toLowerCase()
  const dossierId = asString(row.dossierId ?? row.dossier_id) || dossierFallback
  if (!dossierId) return null
  return {
    dossierId,
    documentId: asString(row.documentId ?? row.document_id) || null,
    sourceFileId: asString(row.sourceFileId ?? row.source_file_id) || null,
    citationId: asString(row.citationId ?? row.citation_id) || null,
    scope: scope === 'annex' || scope === 'body' ? scope : 'unknown',
    status:
      status === 'LOCATABLE' || status === 'PARTIAL' ? status : 'UNRESOLVED',
    quote: asString(row.quote),
    pageNo: asNumber(row.pageNo ?? row.page_no),
    lineId: asString(row.lineId ?? row.line_id) || null,
    bbox: asBbox(row.bbox),
    documentName: asString(row.documentName ?? row.document_name) || null,
    documentRole: asString(row.documentRole ?? row.document_role) || null,
  }
}

function scopeLabel(scope: CitationViewerScope) {
  if (scope === 'annex') return 'Phụ lục'
  if (scope === 'body') return 'Thân hồ sơ'
  return 'Chưa xác định scope'
}

function statusLabel(status: CitationViewerStatus) {
  if (status === 'LOCATABLE') return 'Đã định vị nguồn'
  if (status === 'PARTIAL') return 'Nguồn chưa đủ tọa độ'
  return 'Chưa định vị được nguồn'
}

export function DynamicCitationViewer({
  citation,
}: {
  citation: CitationViewerModel | null
}) {
  if (!citation) {
    return (
      <section className="rounded-xl border border-outline-variant/30 bg-surface-container-lowest p-space-md">
        <h2 className="font-title-sm text-title-sm font-semibold text-primary">
          Citation viewer
        </h2>
        <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
          Chưa chọn citation từ dossier/document cụ thể.
        </p>
      </section>
    )
  }

  const canOpenSource =
    citation.status === 'LOCATABLE' &&
    Boolean(citation.documentId) &&
    citation.pageNo !== null
  const previewUrl = canOpenSource
    ? `${apiBaseUrl}/api/v1/documents/${encodeURIComponent(citation.documentId ?? '')}/pages/${citation.pageNo}/image?variant=preview`
    : null

  return (
    <section
      aria-label="Dynamic citation viewer"
      className="rounded-xl border border-outline-variant/30 bg-surface-container-lowest p-space-md shadow-sm"
      data-citation-status={citation.status}
      data-dossier-id={citation.dossierId}
      data-document-id={citation.documentId ?? ''}
      data-citation-id={citation.citationId ?? ''}
    >
      <div className="flex flex-wrap items-start justify-between gap-space-sm">
        <div>
          <p className="font-label-sm text-label-sm uppercase tracking-wide text-secondary">
            {scopeLabel(citation.scope)} · {statusLabel(citation.status)}
          </p>
          <h2 className="mt-1 font-title-sm text-title-sm font-semibold text-primary">
            {citation.documentName ||
              citation.documentId ||
              'Nguồn chưa xác định'}
          </h2>
        </div>
        <span className="rounded bg-surface-container px-space-xs py-0.5 font-code-sm text-code-sm text-secondary">
          {citation.documentRole || citation.scope}
        </span>
      </div>

      <dl className="mt-space-sm grid gap-x-space-md gap-y-space-xs sm:grid-cols-2 font-code-sm text-code-sm">
        <div>
          <dt className="text-secondary">dossier_id</dt>
          <dd className="break-all text-on-surface">{citation.dossierId}</dd>
        </div>
        <div>
          <dt className="text-secondary">document_id</dt>
          <dd className="break-all text-on-surface">
            {citation.documentId || '—'}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">citation_id</dt>
          <dd className="break-all text-on-surface">
            {citation.citationId || '—'}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">location</dt>
          <dd className="text-on-surface">
            {citation.pageNo ? `Trang ${citation.pageNo}` : '—'}
            {citation.lineId ? ` · ${citation.lineId}` : ''}
          </dd>
        </div>
      </dl>

      <blockquote className="mt-space-sm rounded border border-outline-variant/20 bg-surface-container-low p-space-sm font-body-sm text-body-sm leading-relaxed text-on-surface">
        {citation.quote || 'Không có text span từ backend.'}
      </blockquote>

      {citation.bbox ? (
        <p className="mt-space-xs font-code-sm text-code-sm text-secondary">
          bbox: {citation.bbox.join(', ')}
        </p>
      ) : null}

      {canOpenSource && previewUrl ? (
        <div className="mt-space-sm space-y-space-xs">
          <a
            className="inline-flex rounded bg-primary px-space-sm py-space-xs font-label-sm text-label-sm text-on-primary"
            href={previewUrl}
            target="_blank"
            rel="noreferrer"
          >
            Mở nguồn đã xác minh
          </a>
          <img
            className="max-h-80 w-full rounded border border-outline-variant/30 object-contain"
            src={previewUrl}
            alt={`${citation.documentName || citation.documentId} · trang ${citation.pageNo}`}
          />
        </div>
      ) : (
        <div className="mt-space-sm rounded border border-amber-200 bg-amber-50 p-space-sm font-body-sm text-body-sm text-amber-950">
          Khoảng trống evidence: citation này chưa đủ source scope/page/line để
          xác minh. Không coi đây là liên kết nguồn hợp lệ.
        </div>
      )}
    </section>
  )
}
