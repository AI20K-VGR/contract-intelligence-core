import {
  KIND_LABEL,
  actionLabel,
  formatWhen,
  type TimelineEntry,
} from '../review/timeline'
import { MaterialIcon } from './icons'

/** Dòng thời gian chung của một vị trí: thẩm định trích dẫn và thẩm định xung đột. */
export function ReviewTimeline({
  entries,
  title = 'Lịch sử thẩm định',
}: {
  entries: TimelineEntry[]
  title?: string
}) {
  if (entries.length === 0) return null
  return (
    <div className="mt-2 border-t border-surface-container pt-1">
      <p className="font-label-sm text-label-sm font-semibold uppercase text-secondary">
        {title} ({entries.length})
      </p>
      <ul className="mt-1 flex flex-col gap-1">
        {entries.map((entry) => (
          <li
            key={entry.key}
            className="rounded bg-surface-container-low px-2 py-1 font-body-sm text-body-sm text-on-surface"
          >
            <span className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
              <span
                className={`inline-flex items-center gap-0.5 rounded px-1 font-label-sm text-[10px] font-semibold uppercase tracking-wide ${
                  entry.kind === 'finding'
                    ? 'bg-amber-100 text-amber-900'
                    : 'bg-sky-100 text-sky-900'
                }`}
                title={KIND_LABEL[entry.kind]}
              >
                <MaterialIcon
                  name={entry.kind === 'finding' ? 'warning' : 'fact_check'}
                  className="text-[12px]"
                />
                {KIND_LABEL[entry.kind]}
                {entry.source ? ` · ${entry.source}` : ''}
              </span>
              <span className="font-semibold">{actionLabel(entry.action)}</span>
              <span className="text-on-surface-variant">
                · {entry.who} · {formatWhen(entry.when)}
              </span>
            </span>
            {entry.note ? (
              <span className="block text-on-surface-variant">{entry.note}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
