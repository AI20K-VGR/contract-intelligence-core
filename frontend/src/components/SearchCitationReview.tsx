import { useEffect, useState } from 'react'
import {
  ClauseReviewConflictError,
  getClauseReview,
  saveClauseReview,
  type ClauseReview,
  type ClauseReviewAction,
  type ClauseReviewEntry,
} from '../api/clauseReview'
import type { ClauseNode } from '../api/structure'
import type { SearchCite } from '../structure/citations'
import { bodyOf, headOf, nodeLabel } from '../structure/display'
import { CitationPane } from './CitationPane'
import { MaterialIcon } from './icons'

type Verdict = 'correct' | 'deviation' | 'edit'

const ACTION_OF: Record<Verdict, ClauseReviewAction> = {
  correct: 'confirm',
  deviation: 'reject',
  edit: 'correct',
}

const VERDICT_OF: Record<string, Verdict> = {
  confirm: 'correct',
  reject: 'deviation',
  correct: 'edit',
}

const VERDICT_LABEL: Record<Verdict, string> = {
  correct: 'Chính xác',
  deviation: 'Sai lệch',
  edit: 'Sửa nhận định',
}

function entryNote(entry: ClauseReviewEntry) {
  return entry.assessment ?? entry.comment ?? ''
}

function entryWho(entry: ClauseReviewEntry) {
  return entry.reviewerName || entry.reviewerEmail || entry.reviewerId
}

function entryWhen(entry: ClauseReviewEntry) {
  return entry.createdAt
    ? new Date(entry.createdAt).toLocaleString('vi-VN')
    : ''
}

export function SearchCitationReview({
  citeNo,
  documentId,
  filename,
  node,
  ordinal,
  related,
  onBack,
  onPick,
}: {
  citeNo: number
  documentId: string
  filename: string | null
  node: ClauseNode
  ordinal: number
  related: SearchCite[]
  onBack: () => void
  onPick: (id: string) => void
}) {
  const [verdict, setVerdict] = useState<Verdict>('correct')
  const [note, setNote] = useState('')
  const [saved, setSaved] = useState(false)
  const [review, setReview] = useState<ClauseReview | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const head = headOf(node)
  const body = bodyOf(node) || node.text.replace(/\s+/g, ' ').trim()
  const page = node.pageStart || node.regions[0]?.pageNo || 1
  const others = related.filter((item) => item.id !== node.id)
  const latest = review?.latest ?? null
  const locked = review?.dossierLocked ?? false

  function adopt(next: ClauseReview) {
    setReview(next)
    if (next.latest) {
      setVerdict(VERDICT_OF[next.latest.action] ?? 'correct')
      setNote(entryNote(next.latest))
    } else {
      setVerdict('correct')
      setNote('')
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setSaved(false)
    setMessage(null)
    setReview(null)
    getClauseReview({ documentId, node, ordinal }, controller.signal)
      .then(adopt)
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setMessage(
          cause instanceof Error ? cause.message : 'Không tải được thẩm định.',
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [documentId, node, ordinal])

  function choose(next: Verdict) {
    setVerdict(next)
    setSaved(false)
  }

  async function save() {
    if (saving || loading) return
    if (verdict === 'edit' && !note.trim()) {
      setMessage('Sửa nhận định cần nhập nội dung nhận định mới.')
      return
    }
    setSaving(true)
    setMessage(null)
    try {
      const next = await saveClauseReview({ documentId, node, ordinal }, {
        action: ACTION_OF[verdict],
        baseVersion: review?.version ?? 0,
        comment: note,
      })
      adopt(next)
      setSaved(true)
    } catch (cause: unknown) {
      if (cause instanceof ClauseReviewConflictError && cause.current) {
        adopt(cause.current)
        const who = cause.current.latest ? entryWho(cause.current.latest) : ''
        setMessage(
          `${who || 'Người khác'} vừa lưu thẩm định cho trích dẫn này. Đã tải bản mới nhất, hãy xem lại trước khi lưu.`,
        )
      } else {
        setMessage(
          cause instanceof Error ? cause.message : 'Không lưu được thẩm định.',
        )
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-space-sm">
      <div className="flex flex-wrap items-center gap-space-sm">
        <button
          className="inline-flex items-center gap-1 rounded bg-surface-container-lowest px-3 py-1 font-label-sm text-label-sm text-on-surface shadow-sm hover:bg-surface-container-high"
          type="button"
          onClick={onBack}
        >
          <MaterialIcon name="arrow_back" className="text-[16px]" />
          Quay lại kết quả tìm kiếm
        </button>
        <span className="font-code-sm text-code-sm text-secondary">
          Đối soát trích dẫn [{citeNo}]
          {head ? ` / ${head}` : ''}
        </span>
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-1 items-stretch gap-space-md lg:grid-cols-12">
        <div className="flex flex-col gap-space-sm lg:col-span-5">
          <section className="rounded bg-surface-container-lowest p-space-md shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1">
                <MaterialIcon
                  name="fact_check"
                  className="text-[18px] text-on-tertiary-container"
                />
                <span className="font-label-md text-label-md font-bold uppercase tracking-wide text-on-surface">
                  Thẩm định trích dẫn [{citeNo}]
                </span>
              </div>
              <span className="rounded bg-surface-container px-2 py-0.5 font-code-sm text-code-sm text-on-surface">
                Trang {page}
              </span>
            </div>
            <p className="mt-space-sm rounded border border-surface-container bg-surface-container-low p-space-sm font-body-md text-body-md leading-relaxed text-on-surface">
              {body ? `“${body}”` : 'Không có nội dung trích dẫn.'}
            </p>
            <p className="mt-space-sm font-label-sm text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">
              Nhận định của chuyên viên
            </p>
            {latest ? (
              <p className="mt-1 font-body-sm text-body-sm text-on-surface-variant">
                Lần gần nhất:{' '}
                <span className="font-semibold text-on-surface">
                  {VERDICT_LABEL[VERDICT_OF[latest.action] ?? 'correct']}
                </span>{' '}
                bởi {entryWho(latest)} · {entryWhen(latest)}
              </p>
            ) : !loading ? (
              <p className="mt-1 font-body-sm text-body-sm text-secondary">
                Chưa có ai thẩm định trích dẫn này.
              </p>
            ) : null}
            {review?.stale ? (
              <div className="mt-1 rounded border border-[#F59E0B] bg-[#FFFBEB] p-2 font-body-sm text-body-sm text-on-surface">
                <p className="flex items-center gap-1 font-semibold text-[#92400E]">
                  <MaterialIcon name="history" className="text-[15px]" />
                  Từ lần phân tích trước, cần xem lại
                </p>
                <p className="mt-0.5">
                  <span className="font-semibold">
                    {VERDICT_LABEL[VERDICT_OF[review.stale.latest.action] ?? 'correct']}
                  </span>{' '}
                  bởi {entryWho(review.stale.latest)} · {entryWhen(review.stale.latest)}
                </p>
                {entryNote(review.stale.latest) ? (
                  <p className="mt-0.5 text-on-surface-variant">
                    {entryNote(review.stale.latest)}
                  </p>
                ) : null}
                {review.stale.textChanged ? (
                  <p className="mt-0.5 font-semibold text-[#92400E]">
                    Nội dung điều khoản đã đổi so với lúc thẩm định.
                  </p>
                ) : null}
                <p className="mt-0.5 text-secondary">
                  Kết quả này không được tính cho lần phân tích hiện tại. Hãy chọn nhận định rồi lưu lại.
                </p>
              </div>
            ) : null}
            <div className="mt-1 grid grid-cols-3 gap-1">
              <VerdictButton
                active={verdict === 'correct'}
                icon="check_circle"
                label="Chính xác"
                onClick={() => choose('correct')}
              />
              <VerdictButton
                active={verdict === 'deviation'}
                icon="cancel"
                label="Sai lệch"
                onClick={() => choose('deviation')}
              />
              <VerdictButton
                active={verdict === 'edit'}
                icon="edit_note"
                label="Sửa nhận định"
                onClick={() => choose('edit')}
              />
            </div>
            <textarea
              className="mt-2 w-full resize-none rounded bg-surface-container-low p-2 font-body-sm text-body-sm text-on-surface outline-none focus:ring-1 focus:ring-outline-variant"
              placeholder="Ghi chú thẩm định..."
              rows={2}
              disabled={locked}
              value={note}
              onChange={(event) => {
                setNote(event.target.value)
                setSaved(false)
              }}
            />
            {message ? (
              <p className="mt-1 font-body-sm text-body-sm text-error">{message}</p>
            ) : null}
            <div className="mt-1 flex items-center justify-end gap-2">
              {locked ? (
                <span className="font-label-sm text-label-sm text-secondary">
                  Hồ sơ đã khóa
                </span>
              ) : null}
              <button
                className="inline-flex items-center gap-1 rounded bg-primary px-3 py-1 font-label-sm text-label-sm font-semibold text-on-primary disabled:opacity-50"
                type="button"
                disabled={loading || saving || locked}
                onClick={() => void save()}
              >
                <MaterialIcon name={saved ? 'check' : 'save'} className="text-[15px]" />
                {saving ? 'Đang lưu...' : saved ? 'Đã lưu thẩm định' : 'Lưu thẩm định'}
              </button>
            </div>
            {review && review.history.length > 0 ? (
              <div className="mt-space-sm border-t border-surface-container pt-space-xs">
                <p className="font-label-sm text-label-sm font-semibold uppercase text-secondary">
                  Lịch sử thẩm định ({review.history.length})
                </p>
                <ul className="mt-1 flex flex-col gap-1">
                  {[...review.history].reverse().map((entry) => (
                    <li
                      key={entry.revisionNumber}
                      className="rounded bg-surface-container-low px-2 py-1 font-body-sm text-body-sm text-on-surface"
                    >
                      <span className="font-semibold">
                        {VERDICT_LABEL[VERDICT_OF[entry.action] ?? 'correct']}
                      </span>{' '}
                      · {entryWho(entry)} · {entryWhen(entry)}
                      {entryNote(entry) ? (
                        <span className="block text-on-surface-variant">
                          {entryNote(entry)}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
          <section className="rounded bg-surface-container-lowest p-space-sm shadow-sm">
            <div className="flex items-center justify-between px-1">
              <span className="font-label-sm text-label-sm font-semibold uppercase text-secondary">
                Trích dẫn liên đới
              </span>
              <span className="font-code-sm text-code-sm text-secondary">
                {related.length} điều khoản
              </span>
            </div>
            <button
              className="mt-1 flex w-full items-center justify-between rounded bg-surface-container-low px-2 py-1 text-left"
              type="button"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span className="flex h-4 min-w-4 items-center justify-center rounded bg-primary-container text-[10px] font-bold text-on-primary">
                  {citeNo}
                </span>
                <span className="truncate font-body-sm text-body-sm font-medium text-on-surface">
                  {nodeLabel(node)}
                </span>
              </span>
              <span className="ml-2 shrink-0 font-label-sm text-label-sm font-semibold text-[#059669]">
                Hiện tại
              </span>
            </button>
            {others.map((item) => (
              <button
                key={item.id}
                className="mt-1 flex w-full items-center justify-between rounded px-2 py-1 text-left text-on-surface-variant hover:bg-surface-container-low"
                type="button"
                onClick={() => onPick(item.id)}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className="flex h-4 min-w-4 items-center justify-center rounded bg-surface-container-high text-[10px] font-bold text-on-surface">
                    {item.n}
                  </span>
                  <span className="truncate font-body-sm text-body-sm">
                    Trích dẫn {item.n}
                  </span>
                </span>
                <span className="ml-2 shrink-0 font-label-sm text-label-sm text-secondary">
                  Mở
                </span>
              </button>
            ))}
          </section>
        </div>
        <div className="flex min-h-[480px] overflow-hidden rounded bg-surface-container-lowest shadow-sm lg:col-span-7">
          <CitationPane
            key={node.id}
            embedded
            citeNo={citeNo}
            documentId={documentId}
            filename={filename}
            node={node}
          />
        </div>
      </div>
    </div>
  )
}

function VerdictButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean
  icon: string
  label: string
  onClick: () => void
}) {
  return (
    <button
      className={`flex items-center justify-center gap-1 rounded px-1 py-1 font-label-sm text-label-sm ${
        active
          ? 'bg-primary-container font-semibold text-on-primary shadow-sm'
          : 'bg-surface-container font-medium text-on-surface-variant hover:bg-surface-container-high'
      }`}
      type="button"
      onClick={onClick}
    >
      <MaterialIcon name={icon} className="text-[14px]" />
      {label}
    </button>
  )
}
