import type {
  DossierSearchHit,
  DossierSearchResult,
  DossierSearchState,
} from '../api/structure'
import { MaterialIcon } from './icons'

const stateMeta: Record<
  DossierSearchState,
  { label: string; className: string; icon: string }
> = {
  PASS: {
    label: 'Đủ căn cứ',
    className: 'bg-emerald-50 text-emerald-800',
    icon: 'verified',
  },
  ANSWERED: {
    label: 'Đã trả lời',
    className: 'bg-emerald-50 text-emerald-800',
    icon: 'check_circle',
  },
  NOT_COMPARABLE: {
    label: 'Không so được',
    className: 'bg-surface-container text-on-surface-variant',
    icon: 'compare_arrows',
  },
  NEEDS_REVIEW: {
    label: 'Cần rà soát',
    className: 'bg-amber-50 text-amber-900',
    icon: 'rate_review',
  },
  INSUFFICIENT_EVIDENCE: {
    label: 'Thiếu căn cứ',
    className: 'bg-surface-container text-on-surface-variant',
    icon: 'help',
  },
  BLOCKED: {
    label: 'Bị chặn theo chính sách',
    className: 'bg-error-container text-on-error-container',
    icon: 'block',
  },
}

function hitLocation(hit: DossierSearchHit) {
  const parts: string[] = []
  if (hit.breadcrumb.length > 0) parts.push(hit.breadcrumb.join(' › '))
  if (hit.pageNo) parts.push(`Trang ${hit.pageNo}`)
  if (hit.tableId) parts.push('Bảng')
  return parts.join(' · ')
}

/**
 * Câu trả lời AI2 cho câu hỏi trên thanh search của trang cấu trúc cây.
 * Bấm một trích dẫn để mở đúng chỗ trong cây / trang PDF.
 */
export function StructureSearchResult({
  result,
  searching,
  error,
  activeHit,
  onSelectHit,
  onClose,
}: {
  result: DossierSearchResult | null
  searching: boolean
  error: string | null
  activeHit: number | null
  onSelectHit: (hit: DossierSearchHit) => void
  onClose: () => void
}) {
  const state = result?.state ? stateMeta[result.state] : null

  return (
    <section
      aria-live="polite"
      className="mb-space-md flex flex-col gap-space-sm rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-space-md py-space-md shadow-sm"
    >
      <div className="flex items-start justify-between gap-space-sm">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-container text-primary">
            <MaterialIcon
              name={searching ? 'progress_activity' : 'neurology'}
              className={`text-[18px] ${searching ? 'animate-spin' : ''}`}
            />
          </div>
          <div className="min-w-0">
            <p className="font-title-sm text-title-sm font-semibold text-primary">
              Câu trả lời AI2
            </p>
            {result ? (
              <p className="truncate font-label-sm text-label-sm text-on-surface-variant">
                {result.query}
              </p>
            ) : null}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {state ? (
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-label-sm text-label-sm font-semibold ${state.className}`}
              title={result?.state ?? undefined}
            >
              <MaterialIcon name={state.icon} className="text-[14px]" />
              {state.label}
            </span>
          ) : null}
          {result?.usedLlm ? (
            <span
              className="rounded-full bg-surface-container px-2 py-0.5 font-label-sm text-label-sm text-secondary"
              title="AI2 đã dùng mô hình ngôn ngữ để tổng hợp câu trả lời"
            >
              LLM
            </span>
          ) : null}
          <button
            aria-label="Đóng câu trả lời"
            className="flex h-7 w-7 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container"
            type="button"
            onClick={onClose}
          >
            <MaterialIcon name="close" className="text-[16px]" />
          </button>
        </div>
      </div>

      {searching ? (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Đang hỏi AI2 qua backend…
        </p>
      ) : null}

      {error ? (
        <p
          className="font-body-sm text-body-sm text-on-error-container"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      {result && !searching ? (
        <>
          {result.answer ? (
            <p className="whitespace-pre-wrap font-body-md text-body-md leading-relaxed text-on-surface">
              {result.answer}
            </p>
          ) : (
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              {result.connected
                ? 'AI2 chưa có câu trả lời cho câu hỏi này.'
                : 'AI2 chưa nối được. Backend đã nhận câu hỏi nhưng dịch vụ AI2 không phản hồi (chưa chạy container ai2, hoặc quá thời gian chờ).'}
            </p>
          )}

          {result.notes.length > 0 && !result.answer ? (
            <ul className="flex flex-col gap-0.5 rounded-lg bg-surface-container-low px-space-sm py-space-xs font-code-sm text-[12px] text-on-surface-variant">
              {result.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}

          {result.hits.length > 0 ? (
            <div className="flex flex-col gap-1">
              <p className="flex items-center gap-1.5 font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
                <MaterialIcon name="fact_check" className="text-[16px]" />
                {result.hits.length} trích dẫn · bấm để mở trong cây
              </p>
              <ol className="divide-y divide-outline-variant/20 overflow-hidden rounded-lg border border-outline-variant/20">
                {result.hits.map((hit) => {
                  const active = activeHit === hit.n
                  const location = hitLocation(hit)
                  return (
                    <li key={`${hit.n}-${hit.citationId ?? hit.text}`}>
                      <button
                        className={`flex w-full items-start gap-space-sm px-space-sm py-space-xs text-left transition-colors ${
                          active
                            ? 'bg-surface-container'
                            : 'hover:bg-surface-container-low'
                        }`}
                        type="button"
                        onClick={() => onSelectHit(hit)}
                      >
                        <span
                          className={`mt-0.5 flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full px-1 text-[11px] font-semibold ${
                            active
                              ? 'bg-primary text-on-primary'
                              : 'bg-surface-container-high text-on-surface'
                          }`}
                        >
                          {hit.n}
                        </span>
                        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                          <span className="font-body-sm text-body-sm text-on-surface">
                            “{hit.text}”
                          </span>
                          {location ? (
                            <span className="font-code-sm text-[11px] text-secondary">
                              {location}
                            </span>
                          ) : null}
                        </span>
                        {hit.validationStatus === 'VALID' ? (
                          <span
                            className="mt-0.5 inline-flex shrink-0 items-center gap-0.5 rounded bg-emerald-50 px-1.5 py-0.5 font-label-sm text-[11px] font-semibold text-emerald-800"
                            title="AI2 đã đối chiếu câu trích khớp nguồn OCR"
                          >
                            <MaterialIcon
                              name="verified"
                              className="text-[12px]"
                            />
                            Khớp nguồn
                          </span>
                        ) : null}
                        <MaterialIcon
                          name="arrow_forward"
                          className="mt-0.5 shrink-0 text-[16px] text-outline"
                        />
                      </button>
                    </li>
                  )
                })}
              </ol>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
