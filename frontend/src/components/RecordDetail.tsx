import { useState } from 'react'
import { getInspectorRecord, type InspectorKind } from '../api/inspector'
import { structureErrorMessage } from '../api/structure'

function show(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return JSON.stringify(value)
}

/** Nút "Chi tiết": tải bản ghi đầy đủ của fact, finding hoặc citation theo id. */
export function RecordDetail({
  kind,
  id,
  label = 'Chi tiết',
}: {
  kind: InspectorKind
  id: string
  label?: string
}) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [record, setRecord] = useState<Record<string, unknown> | null>(null)

  async function toggle() {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    if (record || loading) return
    setLoading(true)
    setError(null)
    try {
      setRecord(await getInspectorRecord(kind, id))
    } catch (cause) {
      setError(structureErrorMessage(cause) ?? 'Không tải được chi tiết.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <span className="inline-flex flex-col items-start">
      <button
        aria-expanded={open}
        className="text-primary underline"
        type="button"
        onClick={() => {
          void toggle()
        }}
      >
        {open ? 'Ẩn chi tiết' : label}
      </button>
      {open ? (
        <span className="mt-space-xs block w-full rounded bg-surface-container-low p-space-sm font-code-sm text-code-sm text-on-surface">
          {loading ? 'Đang tải…' : null}
          {error ? <span className="text-error">{error}</span> : null}
          {record ? (
            <dl className="grid gap-x-space-sm gap-y-1 sm:grid-cols-[max-content_1fr]">
              {Object.entries(record).map(([key, value]) => (
                <div className="contents" key={key}>
                  <dt className="text-secondary">{key}</dt>
                  <dd className="break-all">{show(value)}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </span>
      ) : null}
    </span>
  )
}
