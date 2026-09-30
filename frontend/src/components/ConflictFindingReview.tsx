import { useEffect, useMemo, useState } from 'react'
import { getClauseReview, type ClauseReview } from '../api/clauseReview'
import {
  FindingReviewConflictError,
  getFindingReview,
  saveFindingReview,
  type FindingReview,
  type FindingReviewEntry,
} from '../api/findingReview'
import type { ClauseNode } from '../api/structure'
import { reviewerLabel } from '../review/reviewerLabel'
import {
  actionLabel,
  extraNoteLabel,
  mergeTimelines,
  reviewActionOf,
  timelineEntries,
  verdictOfAction,
  type ReviewVerdict,
} from '../review/timeline'
import { MaterialIcon } from './icons'
import { ReviewTimeline } from './ReviewTimeline'

/** Điều khoản trên từng tài liệu mà xung đột này trích dẫn. */
export type LinkedClause = {
  /** "Hợp đồng" | "Phụ lục" */
  label: string
  documentId: string
  node: ClauseNode
  ordinal: number
}

const NO_LINKS: LinkedClause[] = []

function entryNote(entry: FindingReviewEntry) {
  return entry.assessment ?? entry.comment ?? ''
}

function entryWho(entry: FindingReviewEntry) {
  return reviewerLabel(entry)
}

function entryWhen(entry: FindingReviewEntry) {
  return entry.createdAt
    ? new Date(entry.createdAt).toLocaleString('vi-VN')
    : ''
}

export function ConflictFindingReview({
  findingId,
  linkedClauses = NO_LINKS,
  onReviewed,
}: {
  findingId: string
  /** Điều khoản hai bên để kéo lịch sử thẩm định trích dẫn về cùng dòng thời gian. */
  linkedClauses?: LinkedClause[]
  onReviewed?: (reviewed: boolean) => void
}) {
  const [verdict, setVerdict] = useState<ReviewVerdict | null>('dung')
  const [note, setNote] = useState('')
  const [saved, setSaved] = useState(false)
  const [review, setReview] = useState<FindingReview | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [clauseReviews, setClauseReviews] = useState<
    Record<string, ClauseReview>
  >({})
  const latest = review?.latest ?? null
  const locked = review?.dossierLocked ?? false
  const linkKey = linkedClauses
    .map((link) => `${link.documentId}:${link.node.id}:${link.ordinal}`)
    .join('|')

  // Cùng vị trí: thẩm định trích dẫn (khi search) hiện trong lịch sử của xung đột.
  useEffect(() => {
    if (!linkKey) {
      setClauseReviews({})
      return
    }
    const controller = new AbortController()
    for (const link of linkedClauses) {
      const key = `${link.documentId}:${link.node.id}`
      getClauseReview(
        { documentId: link.documentId, node: link.node, ordinal: link.ordinal },
        controller.signal,
      )
        .then((next) => {
          if (controller.signal.aborted) return
          setClauseReviews((current) => ({ ...current, [key]: next }))
        })
        .catch(() => {
          // Không có thẩm định trích dẫn thì phần xung đột vẫn đủ dùng.
        })
    }
    return () => controller.abort()
    // linkedClauses được nhận diện qua linkKey để không gọi lại khi mảng đổi tham chiếu.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkKey])

  const clauseNotes = linkedClauses.flatMap((link) => {
    const state = clauseReviews[`${link.documentId}:${link.node.id}`]?.latest
    return state
      ? [
          `Trích dẫn bên ${link.label.toLowerCase()} đã được ${reviewerLabel(state)} thẩm định ${actionLabel(state.action)}.`,
        ]
      : []
  })

  const timeline = useMemo(
    () =>
      mergeTimelines(
        timelineEntries('finding', '', `finding:${findingId}`, review?.history ?? []),
        ...linkedClauses.map((link) =>
          timelineEntries(
            'citation',
            link.label,
            `clause:${link.documentId}:${link.node.id}`,
            clauseReviews[`${link.documentId}:${link.node.id}`]?.history ?? [],
          ),
        ),
      ),
    [clauseReviews, findingId, linkedClauses, review?.history],
  )

  function adopt(next: FindingReview) {
    setReview(next)
    onReviewed?.(Boolean(next.latest))
    if (next.latest) {
      setVerdict(verdictOfAction(next.latest.action))
      setNote(entryNote(next.latest))
    } else {
      setVerdict('dung')
      setNote('')
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setSaved(false)
    setMessage(null)
    setReview(null)
    getFindingReview(findingId, controller.signal)
      .then(adopt)
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        onReviewed?.(false)
        setMessage(
          cause instanceof Error ? cause.message : 'Không tải được thẩm định.',
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
    // onReviewed is a parent setter; the review is keyed by the finding.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [findingId])

  function choose(next: ReviewVerdict) {
    setVerdict(next)
    setSaved(false)
  }

  async function save() {
    if (saving || loading) return
    if (!verdict) {
      setMessage('Hãy chọn đúng hoặc sai.')
      return
    }
    setSaving(true)
    setMessage(null)
    try {
      const next = await saveFindingReview(findingId, {
        action: reviewActionOf(verdict),
        baseVersion: review?.version ?? 0,
        comment: note,
      })
      adopt(next)
      setSaved(true)
    } catch (cause: unknown) {
      if (cause instanceof FindingReviewConflictError && cause.current) {
        adopt(cause.current)
        const who = cause.current.latest ? entryWho(cause.current.latest) : ''
        setMessage(
          `${who || 'Người khác'} vừa lưu thẩm định cho mục này. Đã tải bản mới nhất, hãy xem lại trước khi lưu.`,
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
    <div className="mt-2 border-t border-outline-variant/30 pt-2">
      {latest ? (
        <p className="mt-1 font-body-sm text-body-sm text-on-surface-variant">
          Lần gần nhất:{' '}
          <span className="font-semibold text-on-surface">
            {actionLabel(latest.action)}
          </span>{' '}
          bởi {entryWho(latest)} · {entryWhen(latest)}
        </p>
      ) : !loading ? (
        <p className="mt-1 font-body-sm text-body-sm text-secondary">
          Chưa có ai thẩm định mục này.
        </p>
      ) : null}
      {clauseNotes.map((line) => (
        <p
          key={line}
          className="mt-0.5 flex items-start gap-1 font-body-sm text-body-sm text-sky-900"
        >
          <MaterialIcon name="fact_check" className="mt-0.5 shrink-0 text-[14px]" />
          <span>{line} Đây là tham khảo, không thay kết luận về xung đột.</span>
        </p>
      ))}
      {review?.stale ? (
        <div className="mt-1 rounded border border-[#F59E0B] bg-[#FFFBEB] p-2 font-body-sm text-body-sm text-on-surface">
          <p className="flex items-center gap-1 font-semibold text-[#92400E]">
            <MaterialIcon name="history" className="text-[15px]" />
            Từ lần phân tích trước, cần xem lại
          </p>
          <p className="mt-0.5">
            <span className="font-semibold">
              {actionLabel(review.stale.latest.action)}
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
              Nội dung xung đột đã đổi so với lúc thẩm định.
            </p>
          ) : null}
          <p className="mt-0.5 text-secondary">
            Kết quả này không được tính cho lần phân tích hiện tại. Hãy chọn đúng hoặc sai rồi lưu lại.
          </p>
        </div>
      ) : null}
      <div className="mt-1 grid grid-cols-2 gap-1">
        <VerdictButton
          active={verdict === 'dung'}
          icon="check_circle"
          label="Đúng"
          onClick={() => choose('dung')}
        />
        <VerdictButton
          active={verdict === 'sai'}
          icon="cancel"
          label="Sai"
          onClick={() => choose('sai')}
        />
      </div>
      <label className="mt-2 block font-label-sm text-label-sm font-semibold text-on-surface-variant">
        {extraNoteLabel(verdict)}
      </label>
      <textarea
        className="mt-1 w-full resize-none rounded bg-surface-container-low p-2 font-body-sm text-body-sm text-on-surface outline-none focus:ring-1 focus:ring-outline-variant"
        placeholder={extraNoteLabel(verdict)}
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
      <ReviewTimeline entries={timeline} />
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
