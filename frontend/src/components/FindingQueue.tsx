import { useState } from 'react'
import {
  ReviewConflictError,
  type ReviewActionType,
  type ReviewItem,
  type ReviewRevision,
} from '../api/review'

export type FindingQueueEntry = {
  item: ReviewItem
  severity: string
  topic: string
  leftEvidence: string
  rightEvidence: string
  revisions: ReviewRevision[]
}

export function FindingQueue({
  entries,
  onAction,
  onReload,
}: {
  entries: FindingQueueEntry[]
  onAction: (
    entry: FindingQueueEntry,
    action: ReviewActionType,
  ) => Promise<void>
  onReload: () => Promise<void>
}) {
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function runAction(entry: FindingQueueEntry, action: ReviewActionType) {
    if (busyId) return
    setBusyId(entry.item.id)
    setError(null)
    try {
      await onAction(entry, action)
      await onReload()
    } catch (cause: unknown) {
      if (cause instanceof ReviewConflictError) {
        const version = cause.currentState?.version
        setError(
          `409 conflict: server version ${String(version ?? 'unknown')}. Hàng đợi chưa được ghi đè; hãy tải lại trước khi thao tác lại.`,
        )
      } else {
        setError(
          cause instanceof Error
            ? cause.message
            : 'Không ghi nhận được action review.',
        )
      }
    } finally {
      setBusyId(null)
    }
  }

  if (entries.length === 0) {
    return (
      <section className="rounded-xl border border-outline-variant/30 bg-surface-container-lowest p-space-md">
        <h2 className="font-title-sm text-title-sm font-semibold text-primary">
          Finding queue
        </h2>
        <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
          Không có finding/review item mở.
        </p>
      </section>
    )
  }

  return (
    <section aria-label="Finding queue" className="space-y-space-sm">
      {error ? (
        <div
          className="rounded border border-red-200 bg-red-50 p-space-sm font-body-sm text-body-sm text-red-950"
          role="alert"
        >
          {error}
        </div>
      ) : null}
      {entries.map((entry) => (
        <article
          key={entry.item.id}
          className="rounded-xl border border-outline-variant/30 bg-surface-container-lowest p-space-md shadow-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-space-xs">
            <div>
              <span className="font-code-sm text-code-sm font-semibold text-error">
                {entry.severity}
              </span>
              <h3 className="mt-1 font-title-sm text-title-sm font-semibold text-on-surface">
                {entry.topic}
              </h3>
            </div>
            <span className="font-code-sm text-code-sm text-secondary">
              base_version: {entry.item.version}
            </span>
          </div>
          <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
            {entry.item.reason}
          </p>
          <div className="mt-space-sm grid gap-space-sm md:grid-cols-2">
            <div className="rounded border border-outline-variant/20 bg-surface-container-low p-space-sm font-body-sm text-body-sm">
              <strong className="block font-label-sm text-label-sm text-secondary">
                Evidence phía trái
              </strong>
              <span>{entry.leftEvidence || 'Chưa có evidence'}</span>
            </div>
            <div className="rounded border border-outline-variant/20 bg-surface-container-low p-space-sm font-body-sm text-body-sm">
              <strong className="block font-label-sm text-label-sm text-secondary">
                Evidence phía phải
              </strong>
              <span>{entry.rightEvidence || 'Chưa có evidence'}</span>
            </div>
          </div>
          <div className="mt-space-sm flex flex-wrap gap-space-xs">
            {(
              [
                ['confirm', 'Xác nhận'],
                ['reject', 'Từ chối'],
                ['needs_more_evidence', 'Cần thêm bằng chứng'],
              ] as const
            ).map(([action, label]) => (
              <button
                key={action}
                className="rounded bg-surface-container px-space-sm py-space-xs font-label-sm text-label-sm text-on-surface disabled:opacity-50"
                type="button"
                disabled={busyId !== null}
                onClick={() => void runAction(entry, action)}
              >
                {busyId === entry.item.id ? 'Đang ghi...' : label}
              </button>
            ))}
          </div>
          <div className="mt-space-md border-t border-outline-variant/20 pt-space-sm">
            <h4 className="font-label-md text-label-md font-semibold text-on-surface">
              Revision audit ({entry.revisions.length})
            </h4>
            {entry.revisions.length === 0 ? (
              <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
                Chưa có revision.
              </p>
            ) : (
              <ol className="mt-space-xs space-y-space-xs">
                {entry.revisions.map((revision) => (
                  <li
                    key={`${revision.revisionNumber}-${revision.createdAt}`}
                    className="font-body-sm text-body-sm text-secondary"
                  >
                    #{revision.revisionNumber} {revision.action} ·{' '}
                    {revision.authorUserId || 'unknown'}
                    {revision.comment ? ` · ${revision.comment}` : ''}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </article>
      ))}
    </section>
  )
}
