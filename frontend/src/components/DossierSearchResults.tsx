import { Link } from 'react-router-dom'
import { useState } from 'react'
import { MaterialIcon } from './icons'
import type { Ai2SearchHit, Ai2SearchResult } from '../api/ai2'
import type { CitationViewerScope } from './DynamicCitationViewer'

export type CitationNavigationState = {
  dossierId: string
  documentId: string | null
  citationId: string | null
  sourceFileId: string | null
  pageNo: number | null
  lineId: string | null
  bbox: [number, number, number, number] | null
  scope: CitationViewerScope
  status: Ai2SearchHit['citation']['status']
  quote: string
}

export function buildCitationNavigationState(
  result: Ai2SearchResult,
  hit: Ai2SearchHit,
  index: number,
): CitationNavigationState {
  void index
  return {
    dossierId: result.dossierId,
    documentId: hit.citation.documentId ?? hit.citation.sourceFileId,
    citationId:
      hit.citation.citationId ?? hit.citation.lineId ?? hit.citation.nodeId,
    sourceFileId: hit.citation.sourceFileId,
    pageNo: hit.citation.pageNo ?? hit.pageNo,
    lineId: hit.citation.lineId,
    bbox: hit.citation.bbox,
    scope: hit.citation.scope ?? 'body',
    status: hit.citation.status,
    quote: hit.citation.quote || hit.text,
  }
}

type DossierSearchResultsProps = {
  result: Ai2SearchResult
  onSelectCitation: (hit: Ai2SearchHit, index: number) => void
}

function citationLabel(hit: Ai2SearchHit) {
  if (hit.citation.status === 'LOCATABLE') return 'Đã định vị nguồn'
  if (hit.citation.status === 'PARTIAL') return 'Nguồn chưa đủ tọa độ'
  return 'Chưa định vị được nguồn'
}

function MatchRow({
  result,
  hit,
  index,
  active,
  onSelect,
}: {
  result: Ai2SearchResult
  hit: Ai2SearchHit
  index: number
  active: boolean
  onSelect: () => void
}) {
  const source =
    [hit.sourceFileId, hit.lineId].filter(Boolean).join(' · ') ||
    'Chưa có source id'
  const statusColor =
    hit.citation.status === 'LOCATABLE'
      ? 'bg-[#ECFDF5] text-[#065F46]'
      : 'bg-amber-50 text-amber-900'

  return (
    <div className="p-space-md flex flex-col sm:flex-row sm:items-center justify-between gap-space-md hover:bg-surface-container-low transition-colors">
      <button
        className="flex items-start gap-space-md flex-1 min-w-0 text-left"
        type="button"
        onClick={onSelect}
      >
        <span
          className={`w-6 h-6 rounded-[9999px] font-semibold text-[12px] flex items-center justify-center flex-shrink-0 mt-0.5 ${
            active
              ? 'bg-primary text-on-primary font-bold'
              : 'bg-surface-container-high text-on-surface'
          }`}
        >
          {index + 1}
        </span>
        <div className="flex flex-col gap-1 min-w-0">
          <p className="font-body-md text-[14px] text-primary font-medium leading-relaxed">
            {hit.text}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-label-sm text-[11px] font-semibold text-secondary uppercase tracking-wide">
              Căn cứ:
            </span>
            <span className="font-code-sm text-[12px] font-semibold text-on-surface bg-surface-container px-2 py-0.5 rounded border border-outline-variant/30">
              {source}
            </span>
            {hit.pageNo !== null ? (
              <span className="font-label-sm text-[11px] text-secondary">
                Trang {hit.pageNo}
              </span>
            ) : null}
          </div>
        </div>
      </button>
      <div className="flex items-center gap-space-md flex-shrink-0 self-end sm:self-center">
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-[11px] font-semibold ${statusColor}`}
        >
          <MaterialIcon
            name={hit.citation.status === 'LOCATABLE' ? 'verified' : 'warning'}
            className="text-[13px]"
          />
          {citationLabel(hit)}
        </span>
        <Link
          className="inline-flex items-center gap-1 text-primary hover:text-on-surface-variant font-label-sm text-label-sm font-semibold hover:underline"
          state={{ citation: buildCitationNavigationState(result, hit, index) }}
          to="/doi-soat-trich-dan"
        >
          <span>Đối soát</span>
          <MaterialIcon name="arrow_forward" className="text-[16px]" />
        </Link>
      </div>
    </div>
  )
}

export function DossierSearchResults({
  result,
  onSelectCitation,
}: DossierSearchResultsProps) {
  const [activeIndex, setActiveIndex] = useState(0)
  const answer = result.answer ?? 'AI2 chưa đủ evidence để trả lời câu hỏi này.'
  const reviewLabel =
    result.reviewState === 'ANSWERED'
      ? 'Đã trả lời từ snapshot'
      : result.reviewState === 'NEEDS_REVIEW'
        ? 'Cần rà soát evidence'
        : 'Chưa đủ evidence'

  function selectCitation(index: number) {
    setActiveIndex(index)
    const hit = result.hits[index]
    if (hit) onSelectCitation(hit, index)
  }

  return (
    <div className="w-full flex flex-col gap-space-md">
      <div className="w-full bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/30 p-space-lg flex flex-col gap-space-md">
        <div className="flex items-center justify-between pb-space-xs border-b border-outline-variant/20">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary">
              <MaterialIcon name="neurology" className="text-[18px]" />
            </div>
            <div>
              <h2 className="font-title-sm text-title-sm font-semibold text-primary">
                Câu trả lời AI2
              </h2>
              <p className="font-label-sm text-label-sm text-secondary">
                {reviewLabel} · {result.hits.length} đoạn evidence
              </p>
            </div>
          </div>
          <span className="font-label-sm text-label-sm text-secondary">
            {result.connected ? 'Snapshot đã kết nối' : 'AI2 chưa kết nối'}
          </span>
        </div>

        <div className="font-body-md text-on-surface leading-relaxed whitespace-pre-wrap">
          {answer}
        </div>
      </div>

      <div className="w-full flex flex-col gap-space-sm">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <MaterialIcon
              name="fact_check"
              className="text-[18px] text-secondary"
            />
            <h3 className="font-title-sm text-[14px] font-semibold text-primary uppercase tracking-wider">
              EVIDENCE TRẢ VỀ
            </h3>
            <span
              className="bg-surface-container-high text-secondary px-2 py-0.5 font-code-sm text-[11px] font-semibold"
              style={{ borderRadius: '9999px' }}
            >
              {result.hits.length}
            </span>
          </div>
          <span className="font-code-sm text-[12px] text-secondary">
            Nhấp vào evidence để mở nguồn trong hồ sơ
          </span>
        </div>

        {result.hits.length > 0 ? (
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm divide-y divide-outline-variant/20 overflow-hidden">
            {result.hits.map((hit, index) => (
              <MatchRow
                key={`${hit.lineId ?? hit.sourceFileId ?? 'hit'}-${index}`}
                result={result}
                hit={hit}
                index={index}
                active={activeIndex === index}
                onSelect={() => selectCitation(index)}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-space-lg text-amber-950">
            Không có evidence locatable cho câu hỏi này. Hãy kiểm tra snapshot
            hoặc chuyển sang rà soát HITL.
          </div>
        )}
      </div>
    </div>
  )
}
