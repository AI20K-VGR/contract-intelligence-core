import type { Ai2SearchResult } from '../api/ai2'
import { MaterialIcon } from './icons'

function aclNotice(decision: string | null | undefined) {
  switch (decision?.toLowerCase()) {
    case 'filtered':
      return 'Một số trích dẫn đã bị ẩn vì bạn không có quyền xem tài liệu nguồn. Câu trả lời có thể thiếu căn cứ.'
    case 'denied':
      return 'Bạn không có quyền xem các trích dẫn của câu trả lời này.'
    default:
      return null
  }
}

function show(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return JSON.stringify(value)
}

/** Cảnh báo lọc quyền và cách AI2 truy hồi, để người dùng biết vì sao thiếu trích dẫn. */
export function SearchAudit({ result }: { result: Ai2SearchResult }) {
  const notice = aclNotice(result.aclDecision)
  const layer = Object.entries(result.retrievalLayer)
  const notes = result.notes ?? []
  if (!notice && layer.length === 0 && notes.length === 0) return null

  return (
    <div className="flex flex-col gap-space-xs">
      {notice ? (
        <p
          className="flex items-start gap-space-xs rounded-lg bg-amber-50 px-space-sm py-space-xs font-body-sm text-body-sm text-amber-950"
          role="status"
        >
          <MaterialIcon name="lock" className="mt-0.5 text-[16px]" />
          {notice}
        </p>
      ) : null}
      {notes.length > 0 ? (
        <ul className="list-disc pl-space-lg font-body-sm text-body-sm text-on-surface-variant">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      {layer.length > 0 ? (
        <details className="rounded-lg border border-outline-variant/30 px-space-sm py-space-xs">
          <summary className="cursor-pointer font-label-sm text-label-sm text-secondary">
            Cách AI2 tìm căn cứ
          </summary>
          <dl className="mt-space-xs grid gap-x-space-sm gap-y-1 font-code-sm text-code-sm sm:grid-cols-[max-content_1fr]">
            {layer.map(([key, value]) => (
              <div className="contents" key={key}>
                <dt className="text-secondary">{key}</dt>
                <dd className="break-all text-on-surface">{show(value)}</dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}
    </div>
  )
}
