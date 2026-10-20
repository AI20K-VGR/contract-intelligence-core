import { useCallback } from 'react'
import type { ClauseRegion } from '../../api/structure'
import { ConflictDocumentPane } from '../ConflictDocumentPane'
import { MaterialIcon } from '../icons'

/** Một đầu của quan hệ: điều khoản nằm ở đâu trên tài liệu. */
export type GraphEvidenceSide = {
  documentId: string | null
  filename: string
  /** Số điều khoản / tên ngắn để ghi trên đầu khung. */
  title: string
  quote: string
  pageNo: number
  regions: ClauseRegion[]
  /** Đang hỏi máy chủ trang của bằng chứng. */
  locating: boolean
  /** Ghi chú khi không khoanh được (vd. không tải được bằng chứng). */
  note: string
}

export type GraphEvidence = {
  relation: string
  source: GraphEvidenceSide
  target: GraphEvidenceSide
}

/**
 * Bằng chứng của một quan hệ như màn đối soát: hai tài liệu xếp trên dưới,
 * khung vàng là điều khoản nguồn, khung xanh là điều khoản đích.
 */
export function GraphEvidencePane({
  evidence,
  onClose,
}: {
  evidence: GraphEvidence
  onClose: () => void
}) {
  return (
    <aside className="flex min-h-0 w-1/2 min-w-0 flex-col border-l border-outline-variant/30 bg-white">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-outline-variant/20 bg-surface-container px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <MaterialIcon name="compare" className="text-[18px] text-primary" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-on-surface">
              Bằng chứng quan hệ · {evidence.relation}
            </p>
            <p className="flex flex-wrap items-center gap-x-3 text-xs text-secondary">
              <span className="inline-flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-sm bg-amber-500" />
                Nguồn
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-sm bg-sky-500" />
                Đích
              </span>
            </p>
          </div>
        </div>
        <button
          aria-label="Đóng bằng chứng"
          className="flex h-8 w-8 items-center justify-center rounded-full text-tone-500 hover:bg-tone-100"
          title="Đóng"
          type="button"
          onClick={onClose}
        >
          <MaterialIcon name="close" className="text-[20px]" />
        </button>
      </div>
      <div className="grid min-h-0 flex-1 grid-rows-2">
        <EvidenceSidePane side={evidence.source} label="Nguồn" mark="amber" />
        <EvidenceSidePane side={evidence.target} label="Đích" mark="sky" />
      </div>
    </aside>
  )
}

function EvidenceSidePane({
  side,
  label,
  mark,
}: {
  side: GraphEvidenceSide
  label: string
  mark: 'amber' | 'sky'
}) {
  // Tìm trong PDF tự cuộn tới trang tìm thấy; ở đây không cần giữ số trang.
  const ignore = useCallback(() => undefined, [])
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden border-b border-outline-variant/50 last:border-b-0">
      <ConflictDocumentPane
        boxLabel={label}
        citeNo={null}
        documentId={side.documentId}
        emptyNote={side.note}
        filename={side.filename}
        locating={side.locating}
        locked
        mark={mark}
        pageCount={0}
        pageNo={side.pageNo}
        quote={side.quote}
        regions={side.regions}
        sourceLabel={side.title ? `${label} · ${side.title}` : label}
        title={side.title}
        onPageChange={ignore}
        onPageCount={ignore}
      />
    </div>
  )
}
